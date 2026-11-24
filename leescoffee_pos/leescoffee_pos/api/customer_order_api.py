"""API công khai cho web đặt món QR của khách (/order/<token>).

    POST /api/method/leescoffee_pos.leescoffee_pos.api.customer_order_api.<tên_hàm>

Tách hẳn khỏi pos_api.py (API nhân viên). Khách KHÔNG có User ERPNext:
- Mã QR dán tại quán = bản ghi `MYPOS Order QR` (token ngẫu nhiên, gắn Branch, tắt được).
- Đăng nhập SĐT + tên -> server cấp `session_token` (HMAC-SHA256, có hạn, thu hồi được qua cache).
  Mọi hàm (trừ get_shop, login) bắt buộc token này.
- "Đơn của tôi" theo KHÁCH (Customer của phiên) + chi nhánh của mã QR + kênh QR, không theo sid,
  để đơn không mất khi đăng xuất/đăng nhập lại. Đơn chờ thanh toán (có payment_code) chỉ phiên tạo ra nó thấy.
- Chỉ thanh toán chuyển khoản qua SePay; KHÔNG đổi điểm (chưa có OTP), chỉ xem điểm/hạng.
- Giá, CTKM, tùy chọn món đều tính lại ở server bằng hàm dùng chung của pos_api.

Quy tắc + mô hình bảo mật: .claude/rules/leescoffee_pos/order-qr.md.
"""

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from contextlib import contextmanager

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, flt, get_datetime, now_datetime

from ..doctype.branch_config.branch_config import get_brand_info
from ..doctype.pos_invoice_hooks.order_cancel import QR_PAY_WINDOW_MINUTES
from . import pos_api as P

CHANNEL_QR = "QR"
DEFAULT_SESSION_TTL_SECONDS = 12 * 3600
SESSION_TTL_SECONDS = DEFAULT_SESSION_TTL_SECONDS
# Sau PAY_WINDOW_MINUTES: khách không thấy/không sinh QR nữa (đơn "Hết hạn"). Mốc khai ở MỘT nơi:
# doctype/pos_invoice_hooks/order_cancel.py (QR_PAY_WINDOW_MINUTES, QR_CLEANUP_GRACE_MINUTES).
# Sau hạn + đệm, job order_cancel.auto_cancel_stale_drafts chuyển đơn sang Cancelled (giữ đơn, lý do ở custom_cancel_reason).
PAY_WINDOW_MINUTES = QR_PAY_WINDOW_MINUTES
MAX_OPEN_DRAFTS = 2  # đơn chờ thanh toán còn hạn tối đa mỗi phiên
MAX_LINES = 30
MAX_QTY_PER_LINE = 20
NOTE_MAX = 200
# "Đơn của tôi": đơn đã thanh toán chưa hoàn thành quá ACTIVE_PAID_HOURS -> chuyển sang Lịch sử (khỏi poll mãi
# khi nhân viên quên bấm "Đã hoàn thành"). Lịch sử: HISTORY_DAYS ngày gần nhất, tối đa HISTORY_LIMIT đơn.
ACTIVE_PAID_HOURS = 24
HISTORY_DAYS = 30
HISTORY_LIMIT = 30

# bucket -> (số lần, trong bao nhiêu giây)
RATE_LIMITS = {
	"shop_ip": (60, 60),
	"login_ip": (10, 600),
	"login_mobile": (5, 600),
	"new_customer_ip": (3, 3600),
	"order_session": (6, 600),
	"order_ip": (20, 600),
	"qr_session": (20, 600),
	"read_session": (120, 60),  # poll 5 giây = 12 lần/phút
	# get_my_orders (lịch sử theo khách): theo SĐT chặt, theo IP rộng (nhiều khách chung wifi quán).
	"orders_mobile": (60, 60),
	"orders_ip": (300, 60),
}

QR_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
# --- Trạng thái đơn hiển thị cho khách (2026-11-20) -------------------------------------------------
# custom_kitchen_status (nội bộ, kitchen_status.py) -> stage + stage_label (+ stage_message) cho khách.
# Khách KHÔNG nhận: lý do nội bộ (kitchen_outcome_reason, custom_cancel_reason), tên nhân viên, giá trị custom_kitchen_status thô,
# cờ tiền về sau hủy (custom_late_payment*).
STAGE_LABELS = {
	"awaiting_payment": "Chờ thanh toán",
	"expired": "Hết hạn thanh toán",
	"cancelled": "Đã hủy / hết hạn",  # chỉ là nhãn: đơn docstatus 2 trả stage "expired" (frontend đã xử lý stage này)
	"queued": "Chưa làm",
	"ready": "Đã làm",
	"done": "Đã hoàn thành",
	"closed": "Đã đóng đơn",  # Khách không nhận (trung tính)
	"failed": "Không thực hiện được",
	"processing": "Đang xử lý",  # trạng thái lạ: nhãn an toàn
}
KITCHEN_STAGE = {
	"Chưa làm": "queued",
	"Đã làm": "ready",
	"Đã hoàn thành": "done",
	"Khách không nhận": "closed",
	"Không thực hiện được": "failed",
}
STAGE_FALLBACK = "processing"
# Thông điệp nổi bật ({invoice} = mã đơn khách đang thấy). Branch có brand_phone -> bản có liên hệ
# ({shop} = brand_name, thiếu thì "quán"; {phone} = brand_phone); không có số -> bản cũ.
STAGE_MESSAGES = {
	"failed": "Quán không thể thực hiện đơn này, vui lòng liên hệ quầy để được hỗ trợ/hoàn tiền. Mã đơn: {invoice}",
}
STAGE_MESSAGES_WITH_PHONE = {
	"failed": "Quán không thể thực hiện đơn này. Vui lòng liên hệ {shop} qua {phone} để được hỗ trợ/hoàn tiền. Mã đơn: {invoice}",
}
SHOP_FALLBACK = "quán"
# Nhóm "Đang xử lý": đơn đang làm / không thực hiện được trong ACTIVE_PAID_HOURS giờ (2026-11-23: bỏ cờ needs_review),
# sau đó sang Lịch sử (thông điệp liên hệ quán vẫn hiện).
STAGES_IN_PROGRESS = ("queued", "ready", "processing", "failed")

MSG_QR_INVALID = "Mã QR không hợp lệ hoặc đã ngưng sử dụng. Vui lòng quét lại mã tại quán."
MSG_SESSION = "Phiên đặt món đã hết hạn. Vui lòng quét lại mã QR và đăng nhập."
MSG_CLOSED = "Quán chưa mở bán. Vui lòng quay lại sau hoặc gọi món tại quầy."
MSG_NOT_FOUND = "Không tìm thấy đơn."

RateLimitError = getattr(frappe, "RateLimitExceededError", frappe.ValidationError)


# ---------------------------------------------------------------------------
# Tiện ích: IP, giới hạn tần suất, chạy với user ca POS
# ---------------------------------------------------------------------------


def _ip():
	return getattr(frappe.local, "request_ip", None) or "local"


def _rate(bucket, ident):
	"""Bộ đếm cửa sổ cố định trong Redis; vượt ngưỡng -> lỗi chung."""
	limit, seconds = RATE_LIMITS[bucket]
	key = frappe.cache.make_key(f"mypos_rl:{bucket}:{ident}")
	count = frappe.cache.incr(key)
	if count == 1:
		frappe.cache.expire(key, seconds)
	if count > limit:
		frappe.throw(_("Bạn thao tác quá nhanh. Vui lòng thử lại sau ít phút."), RateLimitError)


@contextmanager
def _as_user(user):
	"""Tạm chạy với user của ca POS đang mở (owner đơn = thu ngân trực ca, để đóng ca gom được đơn)."""
	prev = frappe.session.user
	frappe.set_user(user)
	try:
		yield
	finally:
		frappe.set_user(prev)


# ---------------------------------------------------------------------------
# Token phiên khách (HMAC, có hạn, thu hồi qua cache)
# ---------------------------------------------------------------------------


def _b64(raw):
	return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text):
	return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _secret():
	from frappe.utils.password import get_encryption_key

	return hashlib.sha256(("mypos-guest-session|" + get_encryption_key()).encode()).digest()


def _signature(body):
	return _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())


def _sid_key(sid):
	return f"mypos_guest_sid:{sid}"


def _cart_key(customer, qr_name):
	"""Khóa lưu giỏ ở localStorage theo (khách + mã QR). Mờ (HMAC), không lộ mã Customer/SĐT."""
	raw = hmac.new(_secret(), f"cart|{customer}|{qr_name}".encode(), hashlib.sha256).digest()
	return _b64(raw[:12])


def _issue_session(customer, qr_name, branch, display_name):
	ttl = cint(SESSION_TTL_SECONDS)
	if ttl <= 0:
		# Redis không nhận expire <= 0 -> dùng mặc định, ghi log để phát hiện cấu hình sai.
		frappe.log_error(
			title="Order QR: SESSION_TTL_SECONDS không hợp lệ",
			message=f"SESSION_TTL_SECONDS={SESSION_TTL_SECONDS!r}, dùng mặc định {DEFAULT_SESSION_TTL_SECONDS}.",
		)
		ttl = DEFAULT_SESSION_TTL_SECONDS
	sid = secrets.token_urlsafe(16)
	exp = int(time.time()) + ttl
	payload = {"sid": sid, "c": customer, "q": qr_name, "b": branch, "n": display_name, "exp": exp}
	body = _b64(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode())
	frappe.cache.set_value(_sid_key(sid), customer, expires_in_sec=ttl)
	return f"{body}.{_signature(body)}", exp


def _deny():
	raise frappe.PermissionError(_(MSG_SESSION))


def _session(token):
	"""Kiểm tra token: chữ ký, hạn, chưa thu hồi, mã QR còn bật + đúng branch, khách còn bật."""
	try:
		body, sig = str(token or "").split(".", 1)
		if not hmac.compare_digest(sig, _signature(body)):
			_deny()
		data = json.loads(_unb64(body))
	except frappe.PermissionError:
		raise
	except Exception:
		_deny()

	if int(data.get("exp") or 0) < time.time():
		_deny()
	sid, customer = data.get("sid"), data.get("c")
	if not sid or frappe.cache.get_value(_sid_key(sid)) != customer:
		_deny()
	qr = frappe.db.get_value("MYPOS Order QR", data.get("q"), ["branch", "enabled"], as_dict=True)
	if not qr or not qr.enabled or qr.branch != data.get("b"):
		_deny()
	if not frappe.db.exists("Customer", {"name": customer, "disabled": 0}):
		_deny()
	return frappe._dict(
		sid=sid, customer=customer, qr=data["q"], branch=data["b"], display_name=data.get("n") or ""
	)


# ---------------------------------------------------------------------------
# Chi nhánh, ca POS, menu, thanh toán
# ---------------------------------------------------------------------------


def _qr_by_token(qr_token):
	token = str(qr_token or "").strip()
	if not QR_TOKEN_RE.match(token):
		return None
	return frappe.db.get_value(
		"MYPOS Order QR", {"token": token, "enabled": 1}, ["name", "branch"], as_dict=True
	)


def _profile(branch, throw=True):
	if not frappe.db.exists("POS Profile", {"branch": branch, "disabled": 0}):
		if throw:
			frappe.throw(_(MSG_CLOSED))
		return None
	return P._get_pos_profile(branch)


def _open_shift(profile, throw=True):
	"""Ca POS đang mở của POS Profile (bất kỳ thu ngân). Không tự mở ca cho khách."""
	rows = frappe.get_all(
		"POS Opening Entry",
		filters={"pos_profile": profile.name, "status": "Open", "docstatus": 1},
		fields=["name", "user"],
		order_by="period_start_date desc",
		limit=1,
	)
	if rows:
		return rows[0]
	if throw:
		frappe.throw(_(MSG_CLOSED))
	return None


def _menu(profile):
	"""Menu của chi nhánh = MYPOS Menu có price_list = POS Profile.selling_price_list."""
	from ..doctype.mypos_menu.mypos_menu import MYPOSMenu

	price_list = profile.get("selling_price_list")
	if not price_list:
		frappe.throw(_("Quán chưa cấu hình bảng giá nên chưa đặt món qua QR được."))
	return price_list, _public_menu(MYPOSMenu.get_menu_with_items(price_list=price_list))


def _public_menu(menus):
	"""Chỉ giữ khóa khách cần; bỏ size chưa có giá, món/menu rỗng."""
	out = []
	for menu in menus or []:
		items = []
		for item in menu.get("items") or []:
			sizes = [
				{"label": s.get("label") or "", "item_code": s["item_code"], "rate": flt(s["rate"])}
				for s in item.get("sizes") or []
				if s.get("item_code") and s.get("rate") is not None
			]
			if not sizes:
				continue
			items.append(
				{
					"name": item.get("name"),
					"image": item.get("image"),
					"template": bool(item.get("template")),
					"sizes": sizes,
					"option_groups": item.get("option_groups") or [],
				}
			)
		if items:
			out.append({"name": menu.get("name"), "menu_name": menu.get("menu_name"), "items": items})
	return out


def _rows(items, menus):
	"""Làm sạch giỏ từ client rồi kiểm tra lại toàn bộ ở server (món thuộc menu, qty, tùy chọn)."""
	if isinstance(items, str):
		try:
			items = json.loads(items)
		except Exception:
			frappe.throw(_("Giỏ hàng không đúng định dạng."))
	if not isinstance(items, list):
		frappe.throw(_("Giỏ hàng không đúng định dạng."))

	clean = []
	for item in items:
		if not isinstance(item, dict):
			continue
		qty = flt(item.get("qty"))
		if qty != int(qty) or qty < 1 or qty > MAX_QTY_PER_LINE:
			frappe.throw(_("Số lượng mỗi món phải từ 1 đến {0}.").format(MAX_QTY_PER_LINE))
		# Chỉ nhận 3 khóa; luôn có "options" -> đi đường kiểm tra MYPOS Option Group.
		clean.append(
			{"item_code": str(item.get("item_code") or "").strip(), "qty": qty, "options": item.get("options") or []}
		)
	if len(clean) > MAX_LINES:
		frappe.throw(_("Mỗi đơn tối đa {0} dòng món.").format(MAX_LINES))

	allowed = {s["item_code"] for m in menus for it in m["items"] for s in it["sizes"]}
	for row in clean:
		if row["item_code"] not in allowed:
			frappe.throw(_("Có món hiện không còn trong menu của quán. Vui lòng tải lại menu."))

	rows = P._normalize_items(clean)
	if not rows:
		frappe.throw(_("Giỏ hàng đang trống."))
	return rows


def _transfer_mode(profile):
	"""Mode of Payment loại Bank có tài khoản: ưu tiên mode có trong POS Profile."""
	modes = [m for m in P._get_payment_modes(profile.company) if m["has_account"] and m["type"] == "Bank"]
	in_profile = {row.mode_of_payment for row in profile.get("payments") or []}
	candidates = [m for m in modes if m["name"] in in_profile] + modes
	if candidates:
		return candidates[0]
	frappe.throw(_("Quán chưa cấu hình thanh toán chuyển khoản. Vui lòng gọi món tại quầy."))


def _require_sepay(branch):
	"""SePay phải bật + đủ VA/ngân hàng + có API key (thiếu key thì webhook bị từ chối -> đơn treo)."""
	from frappe.utils.password import get_decrypted_password

	b = frappe.db.get_value(
		"Branch", branch, ["sepay_enabled", "sepay_va_account", "sepay_bank_code"], as_dict=True
	)
	key = get_decrypted_password("Branch", branch, "sepay_api_key", raise_exception=False)
	if not b or not b.sepay_enabled or not b.sepay_va_account or not b.sepay_bank_code or not key:
		frappe.throw(_("Quán chưa bật thanh toán chuyển khoản. Vui lòng gọi món tại quầy."))


def _no_redeem(redeem_points):
	if cint(flt(redeem_points)) > 0:
		frappe.throw(
			_("Chưa hỗ trợ đổi điểm khi đặt món qua QR (cần xác thực OTP). Vui lòng đổi điểm tại quầy.")
		)


def _loyalty_public(customer, company, order_total=0):
	"""Chỉ điểm + hạng của chính khách; không có đổi điểm."""
	try:
		info = P._loyalty_info(customer, company, order_total)
	except Exception:
		frappe.log_error(title="Order QR: lỗi đọc điểm khách", message=frappe.get_traceback())
		info = None
	if not info:
		return {"enrolled": False, "redeem_enabled": False}
	return {
		"enrolled": True,
		"tier_name": info["tier_name"],
		"loyalty_points": info["loyalty_points"],
		"redeem_enabled": False,
	}


def _shop(branch):
	profile = _profile(branch, throw=False)
	return {
		"brand": get_brand_info(branch),
		"is_open": bool(profile and _open_shift(profile, throw=False)),
		"order_types": list(P.ORDER_TYPES),
		"pay_window_minutes": PAY_WINDOW_MINUTES,
	}


def _clean_text(value, max_len):
	text = re.sub(r"<[^>]*>", "", str(value or ""))
	return re.sub(r"\s+", " ", text).strip()[:max_len]


def _normalize_mobile(raw):
	"""SĐT Việt Nam -> dạng 0xxxxxxxxx (10-11 số). +84/84 đổi về 0. Sai -> None."""
	digits = re.sub(r"\D", "", str(raw or ""))
	if digits.startswith("84") and len(digits) in (11, 12):
		digits = "0" + digits[2:]
	return digits if re.fullmatch(r"0\d{9,10}", digits) else None


def _find_customer(mobile):
	"""Customer đang bật có mobile_number khớp (gồm cả dạng +84/84 lưu từ trước).

	Bỏ qua Customer là khách vãng lai của POS Profile (2026-11-24): khách QR không bao giờ đăng nhập vào khách vãng lai.
	SĐT chỉ khớp khách vãng lai -> lỗi (không tạo khách trùng SĐT).
	"""
	from ..doctype.pos_profile_hooks.pos_profile_hooks import all_walk_in_customers

	variants = [mobile, "+84" + mobile[1:], "84" + mobile[1:]]
	rows = frappe.get_all(
		"Customer",
		filters={"mobile_number": ["in", variants], "disabled": 0},
		pluck="name",
		order_by="creation asc",
		limit=5,
	)
	if not rows:
		return None
	walk_ins = all_walk_in_customers()
	real = [r for r in rows if r not in walk_ins]
	if not real:
		frappe.throw(_("Số điện thoại này không dùng được để đặt món qua QR. Vui lòng liên hệ quầy."))
	return real[0]


# ---------------------------------------------------------------------------
# Đơn của phiên
# ---------------------------------------------------------------------------


def _expires_at(creation):
	return add_to_date(get_datetime(creation), minutes=PAY_WINDOW_MINUTES)


def _expired(creation):
	return now_datetime() >= _expires_at(creation)


def _expires_in(creation):
	"""Số giây còn lại để thanh toán (client đếm ngược, không phụ thuộc đồng hồ máy khách)."""
	return max(0, int((_expires_at(creation) - now_datetime()).total_seconds()))


_ORDER_FIELDS = [
	"name", "order_type", "docstatus", "status", "custom_kitchen_status", "payment_code",
	"grand_total", "rounded_total", "currency", "creation", "order_note",
]


def _own_invoice(s, invoice_name):
	"""Đơn thuộc phiên `s`; không thuộc hoặc không tồn tại -> cùng một lỗi (chống dò mã đơn).

	Gồm cả đơn đã hủy (docstatus 2) để màn thanh toán đang poll thấy "Đã hủy / hết hạn" thay vì lỗi.
	"""
	row = frappe.db.get_value(
		"POS Invoice",
		{"name": str(invoice_name or ""), "guest_session": s.sid, "order_channel": CHANNEL_QR,
			"docstatus": ["in", [0, 1, 2]]},
		_ORDER_FIELDS,
		as_dict=True,
	)
	if not row:
		frappe.throw(_(MSG_NOT_FOUND), frappe.DoesNotExistError)
	return row


def _stage(row):
	if row.docstatus == 2:
		return "expired"  # đã hủy (tay / job hết hạn): khách thấy như hết hạn, không thanh toán được nữa
	if row.docstatus == 0:
		return "expired" if _expired(row.creation) else "awaiting_payment"
	return KITCHEN_STAGE.get(row.custom_kitchen_status or "Chưa làm", STAGE_FALLBACK)


def _stage_message(stage, invoice, brand):
	if stage not in STAGE_MESSAGES:
		return ""
	phone = (brand.get("phone") or "").strip()
	if phone:
		shop = (brand.get("name") or "").strip() or _(SHOP_FALLBACK)
		return _(STAGE_MESSAGES_WITH_PHONE[stage]).format(shop=shop, phone=phone, invoice=invoice)
	return _(STAGE_MESSAGES[stage]).format(invoice=invoice)


def _is_active_paid(row, active_since):
	"""Đơn đã thanh toán còn thuộc nhóm "Đang xử lý" của khách."""
	stage = _stage(row)
	return stage in STAGES_IN_PROGRESS and get_datetime(row.creation) >= active_since


def _orders_payload(s, rows, groups=None):
	"""groups: {invoice_name: "active"|"history"} -> bản tối thiểu cho "Đơn của tôi" (thêm `group`,
	bỏ ghi chú/kitchen_status). Không bao giờ trả payment_code, SĐT, mã Customer, thông tin SePay."""
	from ..doctype.mypos_option_group.option_resolver import read_line_options

	if not rows:
		return []
	names = [r.name for r in rows]
	lines = frappe.get_all(
		"POS Invoice Item",
		filters={"parent": ["in", names], "parenttype": "POS Invoice"},
		fields=["parent", "idx", "item_code", "item_name", "qty", "amount", "options", "sugar_level", "ice_level"],
		order_by="parent asc, idx asc",
	)
	sizes = P._size_labels([ln.item_code for ln in lines])
	by_parent = {}
	for ln in lines:
		by_parent.setdefault(ln.parent, []).append(
			{
				"item_name": ln.item_name,
				"size": sizes.get(ln.item_code, ""),
				"qty": flt(ln.qty),
				"amount": flt(ln.amount),
				"options": read_line_options(ln.options, ln.sugar_level, ln.ice_level),
			}
		)

	brand = {}
	if any(_stage(r) in STAGE_MESSAGES for r in rows):
		brand = get_brand_info(s.branch) or {}  # một lần mỗi request, chỉ khi có đơn cần thông điệp

	out = []
	for r in rows:
		stage = _stage(r)
		minimal = groups is not None
		out.append(
			{
				"invoice_name": r.name,
				"order_type": r.order_type,
				"stage": stage,
				"stage_label": _(STAGE_LABELS["cancelled"] if r.docstatus == 2 else (STAGE_LABELS.get(stage) or STAGE_LABELS[STAGE_FALLBACK])),
				"stage_message": _stage_message(stage, r.name, brand),
				# Không trả giá trị nội bộ (trạng thái pha chế thô); khóa giữ để tương thích, luôn rỗng.
				"kitchen_status": "",
				"customer_name": s.display_name,
				"amount": flt(r.rounded_total or r.grand_total),
				"currency": r.currency,
				"creation": str(r.creation),
				"expires_at": str(_expires_at(r.creation)) if r.docstatus == 0 else None,
				"expires_in": _expires_in(r.creation) if r.docstatus == 0 else None,
				"has_payment_qr": bool(r.payment_code) and stage == "awaiting_payment",
				"order_note": "" if minimal else (r.order_note or ""),
				"items": by_parent.get(r.name, []),
			}
		)
		if minimal:
			out[-1]["group"] = groups.get(r.name, "history")
	return out


def _check_open_drafts(sid):
	since = add_to_date(now_datetime(), minutes=-PAY_WINDOW_MINUTES)
	count = frappe.db.count(
		"POS Invoice",
		{"guest_session": sid, "order_channel": CHANNEL_QR, "docstatus": 0, "creation": [">", since]},
	)
	if count >= MAX_OPEN_DRAFTS:
		frappe.throw(
			_("Bạn đang có đơn chờ thanh toán. Hãy thanh toán hoặc đợi đơn hết hạn ({0} phút).").format(
				PAY_WINDOW_MINUTES
			)
		)


# ---------------------------------------------------------------------------
# API khách (allow_guest)
# ---------------------------------------------------------------------------


@frappe.whitelist(allow_guest=True, methods=["GET", "POST"])
def get_shop(qr_token):
	"""Thông tin quán cho màn đăng nhập (thương hiệu từ Branch, đang mở bán hay không)."""
	_rate("shop_ip", _ip())
	qr = _qr_by_token(qr_token)
	if not qr:
		frappe.throw(_(MSG_QR_INVALID))
	return _shop(qr.branch)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def login(qr_token, mobile, customer_name):
	"""Đăng nhập SĐT + tên. Có Customer theo SĐT -> dùng (không ghi đè tên); chưa có -> tạo mới.

	Không trả về thông tin cho biết SĐT đã có khách hay chưa, không trả tên đã lưu.
	"""
	ip = _ip()
	_rate("login_ip", ip)
	qr = _qr_by_token(qr_token)
	if not qr:
		frappe.throw(_(MSG_QR_INVALID))

	mobile_n = _normalize_mobile(mobile)
	if not mobile_n:
		frappe.throw(_("Số điện thoại không hợp lệ."))
	name = _clean_text(customer_name, 60)
	if len(name) < 2:
		frappe.throw(_("Vui lòng nhập tên (tối thiểu 2 ký tự)."))
	_rate("login_mobile", mobile_n)

	customer = _find_customer(mobile_n)
	if not customer:
		_rate("new_customer_ip", ip)
		customer = P.create_customer(name, mobile_n)["name"]

	token, exp = _issue_session(customer, qr.name, qr.branch, name)
	return {
		"session_token": token,
		"expires_at": exp,
		"customer_name": name,
		"cart_key": _cart_key(customer, qr.name),
		"shop": _shop(qr.branch),
	}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def logout(session_token):
	try:
		s = _session(session_token)
	except frappe.PermissionError:
		return {"ok": True}
	frappe.cache.delete_value(_sid_key(s.sid))
	return {"ok": True}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def get_me(session_token):
	"""Tên hiển thị + điểm/hạng của chính khách + trạng thái quán."""
	s = _session(session_token)
	_rate("read_session", s.sid)
	profile = _profile(s.branch, throw=False)
	return {
		"customer_name": s.display_name,
		"cart_key": _cart_key(s.customer, s.qr),
		"loyalty": _loyalty_public(s.customer, profile.company) if profile else {"enrolled": False, "redeem_enabled": False},
		"shop": _shop(s.branch),
	}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def get_menu(session_token):
	"""Menu của chi nhánh (theo Price List của POS Profile) + option_groups động."""
	s = _session(session_token)
	_rate("read_session", s.sid)
	profile = _profile(s.branch)
	_price_list, menus = _menu(profile)
	return {"menus": menus, "currency": profile.currency or ""}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def preview(session_token, items, redeem_points=0):
	"""Giá sau CTKM do server tính (cùng hàm với POS); không ghi DB, không đổi điểm."""
	s = _session(session_token)
	_rate("read_session", s.sid)
	_no_redeem(redeem_points)
	profile = _profile(s.branch)
	shift = _open_shift(profile)
	price_list, menus = _menu(profile)
	rows = _rows(items, menus)
	mode = _transfer_mode(profile)

	with _as_user(shift.user):
		result = P._pricing_preview(profile, rows, s.customer, price_list, mode, 0)
		loyalty = _loyalty_public(s.customer, profile.company, result["grand_total"])

	result.pop("max_redeem_points", None)
	for row in result["items"]:
		row["rules"] = [{"title": r["title"]} for r in row.get("rules") or []]
	result["loyalty"] = loyalty
	return result


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_order(session_token, items, order_type, order_note=None, redeem_points=0):
	"""Tạo POS Invoice Draft kênh QR (không thẻ rung, không đổi điểm). Thanh toán: create_payment_qr."""
	s = _session(session_token)
	_rate("order_session", s.sid)
	_rate("order_ip", _ip())
	_no_redeem(redeem_points)
	if order_type not in P.ORDER_TYPES:
		frappe.throw(_("Loại đơn không hợp lệ."))
	_check_open_drafts(s.sid)

	profile = _profile(s.branch)
	shift = _open_shift(profile)
	_require_sepay(s.branch)
	price_list, menus = _menu(profile)
	rows = _rows(items, menus)
	mode = _transfer_mode(profile)
	note = _clean_text(order_note, NOTE_MAX)

	with _as_user(shift.user):
		invoice = P._build_invoice(profile, rows, order_type, s.customer, price_list, mode, note)
		invoice.order_channel = CHANNEL_QR
		invoice.qr_source = s.qr
		invoice.guest_session = s.sid
		invoice.redeemed_points = 0
		invoice.buzzer = None
		try:
			invoice.insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(title="Order QR: không tạo được đơn", message=frappe.get_traceback())
			frappe.throw(_("Không tạo được đơn. Vui lòng thử lại hoặc gọi món tại quầy."))

	row = _own_invoice(s, invoice.name)
	return _orders_payload(s, [row])[0]


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_payment_qr(session_token, invoice_name):
	"""VietQR chuyển khoản cho đơn Draft còn hạn của phiên (idempotent: gọi lại trả mã cũ)."""
	from ..doctype.sepay.sepay import generate_qr_for_invoice

	s = _session(session_token)
	_rate("qr_session", s.sid)
	row = _own_invoice(s, invoice_name)
	if row.docstatus == 2:
		frappe.throw(_("Đơn đã hủy hoặc hết hạn. Vui lòng đặt lại."))
	if row.docstatus != 0:
		frappe.throw(_("Đơn đã được thanh toán."))
	if _expired(row.creation):
		frappe.throw(_("Đơn đã hết hạn thanh toán. Vui lòng đặt lại."))

	profile = _profile(s.branch)
	shift = _open_shift(profile)
	_require_sepay(s.branch)
	with _as_user(shift.user):
		res = generate_qr_for_invoice(row.name)

	return {
		"invoice_name": row.name,
		"qr_url": res.get("qr_url") or "",
		"payment_code": res.get("payment_code") or "",
		"amount": flt(res.get("amount")),
		"expires_at": str(_expires_at(row.creation)),
		"expires_in": _expires_in(row.creation),
	}


def _mobile_of(customer):
	"""SĐT của khách (cho giới hạn tần suất theo SĐT); không có thì dùng mã Customer."""
	return frappe.db.get_value("Customer", customer, "mobile_number") or customer


@frappe.whitelist(allow_guest=True, methods=["POST"])
def get_my_orders(session_token, limit=None):
	"""'Đơn của tôi' theo khách + chi nhánh của mã QR + kênh QR (không theo sid).

	- active: đơn Draft CÒN HẠN của chính phiên này (chỉ phiên tạo đơn thấy đơn chờ thanh toán);
	  đơn đã thanh toán Chưa làm/Đã làm trong ACTIVE_PAID_HOURS giờ.
	- history: đơn đã thanh toán còn lại trong HISTORY_DAYS ngày, tối đa HISTORY_LIMIT đơn, mới nhất trước.
	Draft hết hạn / của phiên khác, đơn trả hàng, đơn chi nhánh khác: không trả.
	`limit` giữ cho tương thích chữ ký cũ, không dùng.
	"""
	s = _session(session_token)
	_rate("read_session", s.sid)
	_rate("orders_ip", _ip())
	_rate("orders_mobile", _mobile_of(s.customer))

	qr_names = frappe.get_all("MYPOS Order QR", filters={"branch": s.branch}, pluck="name")
	if not qr_names:
		return []
	now = now_datetime()
	base = {"customer": s.customer, "order_channel": CHANNEL_QR, "qr_source": ["in", qr_names]}

	drafts = frappe.get_all(
		"POS Invoice",
		filters={**base, "docstatus": 0, "guest_session": s.sid,
			"creation": [">", add_to_date(now, minutes=-PAY_WINDOW_MINUTES)]},
		fields=_ORDER_FIELDS,
		order_by="creation desc",
		limit=MAX_OPEN_DRAFTS * 5,
	)
	paid = frappe.get_all(
		"POS Invoice",
		filters={**base, "docstatus": 1, "is_return": 0,
			"creation": [">=", add_to_date(now, days=-HISTORY_DAYS)]},
		fields=_ORDER_FIELDS,
		order_by="creation desc",
		limit=HISTORY_LIMIT + 50,
	)

	active_since = add_to_date(now, hours=-ACTIVE_PAID_HOURS)
	groups, active, history = {}, list(drafts), []
	for r in drafts:
		groups[r.name] = "active"
	for r in paid:
		if _is_active_paid(r, active_since):
			groups[r.name] = "active"
			active.append(r)
		elif len(history) < HISTORY_LIMIT:
			groups[r.name] = "history"
			history.append(r)
	return _orders_payload(s, active + history, groups)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def get_order(session_token, invoice_name):
	s = _session(session_token)
	_rate("read_session", s.sid)
	return _orders_payload(s, [_own_invoice(s, invoice_name)])[0]


# ---------------------------------------------------------------------------
# Scheduled job (hooks.scheduler_events, cron 5 phút)
# ---------------------------------------------------------------------------


def cleanup_expired_qr_orders(older_than_minutes=None):
	"""Hủy (chuyển Cancelled) đơn QR Draft chưa thanh toán quá QR_PAY_WINDOW_MINUTES + QR_CLEANUP_GRACE_MINUTES. Idempotent.

	Giữ tên hàm để tương thích (self-test cũ). Job định kỳ gọi order_cancel.auto_cancel_stale_drafts (gồm cả phần này).
	Chỉ: docstatus = 0, order_channel = QR, không phải trả hàng, payment_status khác "Đã thanh toán".
	"""
	from ..doctype.pos_invoice_hooks.order_cancel import auto_cancel_qr_drafts

	return auto_cancel_qr_drafts(None if older_than_minutes is None else cint(older_than_minutes))
