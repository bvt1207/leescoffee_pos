"""REST API cho giao diện POS (React/TSX).

Mọi hàm trong module này được Frappe v16 expose tự động tại:

    POST /api/method/leescoffee_pos.leescoffee_pos.api.pos_api.<tên_hàm>

Nguyên tắc (theo CLAUDE.md):
- Không hardcode tên thương hiệu / tên chi nhánh / tên Mode of Payment:
  mọi thứ đọc từ DocType cấu hình (Branch, POS Profile, Mode of Payment).
- Không sửa DocType lõi của ERPNext — chỉ dùng POS Invoice theo cách
  ERPNext vốn dùng (create/submit), tận dụng sẵn hook của app.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, get_system_timezone, getdate, now_datetime, nowdate

from ..doctype.branch_config.branch_config import (
    get_brand_info,
    resolve_pos_profile_name,
)

ORDER_TYPES = ("Take Away", "Dine In")
ORDER_CHANNEL = "POS"
WALK_IN = "Walk-in Customer"
LEVELS = (50, 70, 100)
# Trạng thái pha chế: MỘT nơi ở doctype/pos_invoice_hooks/kitchen_status.py (bước tiến + trạng thái kết thúc).
from ..doctype.pos_invoice_hooks.kitchen_status import KITCHEN_FLOW, KITCHEN_TERMINAL_STATUSES  # noqa: E402
# Tên Item Attribute dùng làm size (khớp mypos_menu.py).
SIZE_ATTRIBUTE = "Size"

# ---------------------------------------------------------------------------
# Phân quyền màn POS theo role — NGUỒN DUY NHẤT (frontend đọc qua get_pos_config).
# Đổi quyền (vd. cho KITCHEN thấy cả 3 tab) chỉ sửa các hằng dưới đây.
# Khóa: "manager" | "cashier" | "kitchen" (xem _pos_roles). User nhiều role = hợp quyền.
# ---------------------------------------------------------------------------
ROLE_MANAGER = "POS MANAGER"
ROLE_CASHIER = "POS CASHIER"
ROLE_KITCHEN = "POS KITCHEN"
# Role ngoài app được tính là manager.
MANAGER_EQUIVALENT_ROLES = ("System Manager", "Administrator")

# Mục điều hướng: "sell" = Bán món (/), "orders" = Đơn hàng, "kitchen" = Pha chế.
NAV_ORDER = ["sell", "orders", "kitchen"]
NAV_BY_ROLE = {
	"manager": ["sell", "orders", "kitchen"],
	"cashier": ["sell", "orders", "kitchen"],
	"kitchen": ["kitchen"],
}
# Tab trạng thái được xem ở màn Pha chế.
KITCHEN_TABS_BY_ROLE = {
	"manager": ["Chưa làm", "Đã làm", "Đã hoàn thành"],
	"cashier": ["Đã làm", "Đã hoàn thành"],
	"kitchen": ["Chưa làm", "Đã hoàn thành"],
}
# Bước được chuyển (từ, sang).
KITCHEN_TRANSITIONS_BY_ROLE = {
	"manager": [("Chưa làm", "Đã làm"), ("Đã làm", "Đã hoàn thành")],
	"cashier": [("Đã làm", "Đã hoàn thành")],
	"kitchen": [("Chưa làm", "Đã làm")],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pos_roles(user=None):
	"""{manager, cashier, kitchen} của user (System Manager / Administrator = manager)."""
	user = user or frappe.session.user
	roles = set(frappe.get_roles(user))
	return {
		"manager": user == "Administrator"
		or ROLE_MANAGER in roles
		or bool(roles.intersection(MANAGER_EQUIVALENT_ROLES)),
		"cashier": ROLE_CASHIER in roles,
		"kitchen": ROLE_KITCHEN in roles,
	}


def _union_by_role(mapping, roles, order):
	"""Hợp các danh sách trong mapping theo role đang có, giữ thứ tự `order`."""
	got = set()
	for key, enabled in roles.items():
		if enabled:
			got.update(mapping.get(key, []))
	return [x for x in order if x in got]


def _kitchen_tabs(roles=None):
	return _union_by_role(KITCHEN_TABS_BY_ROLE, roles or _pos_roles(), KITCHEN_FLOW)


def _kitchen_transitions(roles=None):
	roles = roles or _pos_roles()
	pairs = set()
	for key, enabled in roles.items():
		if enabled:
			pairs.update(KITCHEN_TRANSITIONS_BY_ROLE.get(key, []))
	return sorted(pairs, key=lambda p: KITCHEN_FLOW.index(p[0]))


def _require_pos_role(roles):
	if not any(roles.values()):
		frappe.throw(
			_("Tài khoản chưa được gán role POS (POS MANAGER / POS CASHIER / POS KITCHEN)."),
			frappe.PermissionError,
		)


def _require_sale_role():
	"""Chỉ thu ngân / quản lý được tạo đơn, thu tiền, hủy đơn.

	Cho phép: POS MANAGER, POS CASHIER, System Manager, Administrator (_pos_roles: hai role sau tính là
	manager). POS KITCHEN (kể cả khi vào được Desk) bị chặn.
	"""
	roles = _pos_roles()
	if not (roles["manager"] or roles["cashier"]):
		frappe.throw(
			_("Bạn không có quyền thực hiện thao tác bán hàng (cần role POS CASHIER hoặc POS MANAGER)."),
			frappe.PermissionError,
		)


def _get_pos_profile(branch_name=None):
	"""Trả về POS Profile đang dùng.

	- Có `branch_name`: POS Profile đang bật của chi nhánh đó, không có thì throw.
	- Không có: `resolve_pos_profile_name()` (POS Profile gán cho user, hoặc
	  POS Profile đang bật duy nhất; không xác định được thì throw).
	"""
	if branch_name:
		profile_name = frappe.db.get_value(
			"POS Profile",
			{"branch": branch_name, "disabled": 0},
			"name",
		)
		if not profile_name:
			frappe.throw(
				_("Chi nhánh {0} chưa có POS Profile đang bật. Vui lòng tạo POS Profile và gán Branch.").format(
					branch_name
				)
			)
	else:
		profile_name = resolve_pos_profile_name()

	return frappe.get_doc("POS Profile", profile_name)


def _company_warnings(profile):
	"""Cảnh báo (không chặn) khi Branch.company khác POS Profile.company."""
	branch = getattr(profile, "branch", None)
	if not branch:
		return []
	branch_company = frappe.db.get_value("Branch", branch, "company")
	if not branch_company or branch_company == profile.company:
		return []
	msg = _("Chi nhánh {0} thuộc công ty {1}, nhưng POS Profile {2} thuộc công ty {3}.").format(
		branch, branch_company, profile.name, profile.company
	)
	frappe.log_error(title="Leescoffee POS: lệch company Branch/POS Profile", message=msg)
	return [msg]


def _get_payment_modes(company):
	"""Danh sách Mode of Payment đang bật, kèm tài khoản mặc định của company."""
	modes = frappe.get_all(
		"Mode of Payment",
		filters={"enabled": 1},
		fields=["name", "type"],
		order_by="name asc",
	)

	result = []
	for mode in modes:
		account = frappe.db.get_value(
			"Mode of Payment Account",
			{"parent": mode.name, "company": company},
			"default_account",
		)
		result.append(
			{
				"name": mode.name,
				"label": mode.name,
				"type": mode.type,
				"account": account or "",
				"has_account": bool(account),
			}
		)

	return result


def _resolve_mode_of_payment(company, mode_of_payment=None):
	"""Chọn Mode of Payment hợp lệ (có tài khoản mặc định cho company)."""
	modes = _get_payment_modes(company)

	if mode_of_payment:
		for mode in modes:
			if mode["name"] == mode_of_payment:
				if not mode["has_account"]:
					frappe.throw(
						_(
							"Phương thức thanh toán {0} chưa có tài khoản mặc định cho công ty. "
							"Vui lòng cấu hình trong Mode of Payment."
						).format(mode_of_payment)
					)
				return mode

		frappe.throw(_("Phương thức thanh toán {0} không tồn tại.").format(mode_of_payment))

	usable = [mode for mode in modes if mode["has_account"]]
	if not usable:
		frappe.throw(
			_(
				"Chưa có Mode of Payment nào được cấu hình tài khoản mặc định cho công ty. "
				"Vui lòng cấu hình trong Mode of Payment."
			)
		)

	return usable[0]

def _level(value):
	"""Đường/đá chỉ nhận 50/70/100, mặc định 100. Trả chuỗi cho field Select."""
	try:
		v = int(flt(value))
	except Exception:
		v = 100
	return str(v if v in LEVELS else 100)

def _legacy_input(item, short, field):
	"""Giá trị đường/đá kiểu cũ nếu request gửi (khóa 'sugar'/'ice' hoặc 'sugar_level'/'ice_level')."""
	for key in (short, field):
		if item.get(key) not in (None, ""):
			return _level(item.get(key))
	return None


def _normalize_items(items):
	"""Chuẩn hóa danh sách món gửi từ giao diện.

	- Dòng KHÔNG có khóa "options" (frontend cũ): giữ nguyên hành vi cũ, đường/đá mặc định 100.
	- Dòng CÓ khóa "options" (kể cả rỗng): kiểm tra theo MYPOS Option Group áp dụng cho món,
	  lưu JSON vào POS Invoice Item.options; cột cũ chỉ ghi khi nhóm có legacy_field
	  (hoặc request gửi rõ sugar/ice). Không đổi giá (không phụ thu).
	"""
	from ..doctype.mypos_option_group.option_resolver import resolve_option_groups, validate_line_options

	if isinstance(items, str):
		items = frappe.parse_json(items)

	normalized, pending = [], []

	for item in items or []:
		if not isinstance(item, dict):
			continue

		item_code = (item.get("item_code") or "").strip()
		if not item_code:
			continue

		qty = flt(item.get("qty"))
		if qty <= 0:
			continue

		row = {
			"item_code": item_code,
			"qty": qty,
			"uom": item.get("uom") or "",
		}

		if "options" in item:
			for short, field in (("sugar", "sugar_level"), ("ice", "ice_level")):
				value = _legacy_input(item, short, field)
				if value is not None:
					row[field] = value
			pending.append((row, item.get("options")))
		else:
			row["sugar_level"] = _level(item.get("sugar"))
			row["ice_level"] = _level(item.get("ice"))

		if item.get("warehouse"):
			row["warehouse"] = item.get("warehouse")

		normalized.append(row)

	if pending:
		# Một lần giải quyết nhóm cho mọi dòng có options (không query trong vòng lặp).
		import json

		from ..doctype.mypos_option_group.option_resolver import item_names

		codes = [r["item_code"] for r, _raw in pending]
		groups_by_code = resolve_option_groups(codes)
		names = item_names(codes)
		for row, raw in pending:
			code = row["item_code"]
			options, legacy = validate_line_options(raw, groups_by_code.get(code, []), names.get(code) or code)
			row["options"] = json.dumps(options, ensure_ascii=False, separators=(",", ":"))
			row.update(legacy)

	return normalized


def _resolve_customer(customer=None):
	"""Nhận MÃ Customer đã tồn tại; trống thì dùng khách vãng lai."""
	customer = str(customer or "").strip()
	if not customer:
		customer = WALK_IN
	if not frappe.db.exists("Customer", customer):
		frappe.throw(
			_("Khách hàng {0} không tồn tại. Hãy chọn khách có sẵn hoặc tạo mới.").format(customer)
		)
	return customer


def _ensure_opening_entry(profile):
	"""Đảm bảo có POS Opening Entry 'Open' để tạo được POS Invoice.

	ERPNext bắt buộc điều này khi tạo POS Invoice
	(validate_pos_opening_entry trong erpnext/accounts/doctype/sales_invoice).

	Ưu tiên dùng lại phiên POS đang mở của user hiện tại (docstatus=1,
	status=Open); không lọc theo ngày — cho phép tái dùng phiên mở của
	người dùng (VD: mở app trên một máy tính ngày trước) mà không bị
	ERPNext phát hiện là "phiên đã cũ" (Outdated). Nếu chưa có phiên mở
	của user, tạo phiên mới.
	"""
	existing = frappe.get_all(
		"POS Opening Entry",
		filters={
			"pos_profile": profile.name,
			"user": frappe.session.user,
			"status": "Open",
			"docstatus": 1,
		},
		fields=["name", "period_start_date"],
		order_by="period_start_date desc",
		limit=1,
	)

	if existing:
		return existing[0].name

	try:
		opening = frappe.get_doc(
			{
				"doctype": "POS Opening Entry",
				"period_start_date": now_datetime(),
				"posting_date": nowdate(),
				"user": frappe.session.user,
				"pos_profile": profile.name,
				"company": profile.company,
			}
		)
		opening.insert(ignore_permissions=True)
		opening.submit()
	except Exception as e:
		# Giữ lý do gốc (vd. "Ca của … chưa đóng", user không thuộc Applicable for Users — pos_shift_hooks).
		reason = frappe.utils.strip_html(str(e)).strip()
		frappe.clear_messages()
		frappe.throw(
			_(
				"Không mở được phiên POS cho POS Profile {0}. "
				"Vui lòng mở phiên POS (POS Opening Entry) trong Desk."
			).format(profile.name)
			+ (f" {_('Lý do')}: {reason}" if reason else "")
		)

	return opening.name


def _assign_buzzer(profile, buzzer=None):
	"""Gán thẻ bàn (kỹ thuật: MYPOS Buzzer) cho đơn Dine In. Thẻ do cashier chọn, được kiểm tra lại.

	2026-11-23: "đang dùng" tính theo ĐƠN CÒN GIỮ (Draft / đã thanh toán, pha chế chưa kết thúc) — không đọc field
	status của thẻ, để thẻ kẹt "Đang dùng" (dữ liệu cũ, sửa tay) không bị khóa mãi.
	"""
	branch = getattr(profile, "branch", None)
	if not branch:
		frappe.throw(_("POS Profile {0} chưa được gán chi nhánh nên chưa thể gán thẻ bàn.").format(profile.name))
	if not buzzer:
		frappe.throw(_("Đơn tại quán cần chọn thẻ bàn."))

	data = frappe.db.get_value("MYPOS Buzzer", buzzer, ["branch", "buzzer_number"], as_dict=True)
	if not data or data.branch != branch:
		frappe.throw(_("Thẻ bàn {0} không thuộc chi nhánh {1}.").format(buzzer, branch))

	holder = _held_buzzers([buzzer]).get(buzzer)
	if holder:
		frappe.throw(_("Thẻ bàn số {0} đang giữ cho đơn {1}.").format(data.buzzer_number, holder))
	return buzzer


def _held_buzzers(buzzers=None):
	"""{thẻ: đơn đang giữ}. Giữ = đơn Dine In docstatus 0/1 có thẻ, pha chế chưa kết thúc (đơn Cancelled = docstatus 2 không giữ).

	Nguồn sự thật duy nhất cho "thẻ đang dùng" (get_buzzers, _assign_buzzer)."""
	filters = {"order_type": "Dine In", "docstatus": ["in", [0, 1]], "buzzer": ["is", "set"]}
	if buzzers is not None:
		filters["buzzer"] = ["in", list(buzzers)]
	held = {}
	for r in frappe.get_all("POS Invoice", filters=filters, fields=["name", "buzzer", "custom_kitchen_status"],
			order_by="creation asc"):
		if (r.custom_kitchen_status or "") not in KITCHEN_TERMINAL_STATUSES:
			held.setdefault(r.buzzer, r.name)
	return held


def _buzzer_number(buzzer_name):
	if not buzzer_name:
		return None

	return frappe.db.get_value("MYPOS Buzzer", buzzer_name, "buzzer_number")


def _size_labels(item_codes):
	"""{variant item_code: nhãn size} — một truy vấn cho cả đơn.

	Nhãn = abbr của Item Attribute Value, rỗng thì lấy attribute_value.
	Món không phải variant (hoặc không có thuộc tính Size) không có trong kết quả.
	"""
	codes = list({c for c in item_codes if c})
	if not codes:
		return {}

	rows = frappe.db.sql(
		"""
		SELECT iva.parent AS item_code,
			COALESCE(NULLIF(iav.abbr, ''), iva.attribute_value) AS size
		FROM `tabItem Variant Attribute` iva
		INNER JOIN `tabItem` i
			ON i.name = iva.parent AND IFNULL(i.variant_of, '') != ''
		LEFT JOIN `tabItem Attribute Value` iav
			ON iav.parent = iva.attribute AND iav.attribute_value = iva.attribute_value
		WHERE iva.parenttype = 'Item'
			AND iva.attribute = %(attr)s
			AND iva.parent IN %(codes)s
		""",
		{"attr": SIZE_ATTRIBUTE, "codes": codes},
		as_dict=True,
	)
	return {r.item_code: r.size or "" for r in rows}

def _record_redemption(invoice, points=None):
	"""Ghi dòng điểm âm khi đơn có đổi điểm."""
	if points is None:
		points = invoice.get("redeemed_points")
	points = int(flt(points))
	if points <= 0 or not invoice.customer:
		return

	lp = frappe.db.get_value("Customer", invoice.customer, "loyalty_program")
	if not lp:
		return

	# Chống ghi trùng nếu hàm bị gọi lại
	if frappe.db.exists("Loyalty Point Entry", {
		"invoice_type": "POS Invoice", "invoice": invoice.name, "loyalty_points": ["<", 0],
	}):
		return

	entry = frappe.new_doc("Loyalty Point Entry")
	entry.loyalty_program = lp
	entry.customer = invoice.customer
	entry.invoice_type = "POS Invoice"
	entry.invoice = invoice.name
	entry.loyalty_points = -points
	entry.purchase_amount = 0
	entry.posting_date = invoice.posting_date
	# Hạn dòng âm = hạn của điểm tích (posting_date + expiry_duration), để ERPNext
	# không bỏ dòng âm khỏi số dư từ ngày hôm sau.
	duration = cint(frappe.db.get_value("Loyalty Program", lp, "expiry_duration")) or 365
	entry.expiry_date = add_days(invoice.posting_date, duration)
	entry.company = invoice.company
	entry.discretionary_reason = f"Đổi điểm trên hóa đơn {invoice.name}"
	entry.insert(ignore_permissions=True)


def _loyalty_info(customer, company, order_total=0):
	"""Thông tin tích điểm của khách; None nếu Walk-in hoặc chưa có chương trình.

	max_redeem_points = min(điểm hiện có, floor(order_total / conversion_factor)).
	"""
	if not customer or customer == WALK_IN:
		return None

	lp = frappe.db.get_value("Customer", customer, "loyalty_program")
	if not lp:
		return None

	from erpnext.accounts.doctype.loyalty_program.loyalty_program import (
		get_loyalty_program_details_with_points,
	)

	details = get_loyalty_program_details_with_points(customer, loyalty_program=lp, company=company)
	points = int(flt(details.get("loyalty_points")))
	cf = flt(frappe.db.get_value("Loyalty Program", lp, "conversion_factor"))
	by_total = int(flt(order_total) // cf) if cf > 0 else 0

	return {
		"program": lp,
		"tier_name": details.get("tier_name") or "",
		"loyalty_points": points,
		"total_spent": flt(details.get("total_spent")),
		"conversion_factor": cf,
		"collection_factor": flt(details.get("collection_factor")),
		"max_redeem_points": max(0, min(points, by_total)),
	}


def _apply_redemption(invoice, customer, company, redeem_points):
	"""Đổi điểm = giảm thẳng trên Grand Total (gọi sau _build_invoice, trước insert).

	Tổng làm gốc là grand_total SAU Pricing Rule. Không dùng redeem_loyalty_points gốc
	của ERPNext; dòng điểm âm ghi ở on_submit.
	"""
	redeem = int(flt(redeem_points))
	if redeem <= 0:
		return

	pre_total = flt(invoice.grand_total)
	info = _loyalty_info(customer, company, pre_total)
	if not info:
		frappe.throw(
			_("Khách {0} chưa tham gia chương trình tích điểm, không đổi điểm được.").format(customer)
		)

	if redeem > info["max_redeem_points"]:
		frappe.throw(
			_(
				"Chỉ đổi được tối đa {0} điểm (khách có {1} điểm, 1 điểm = {2} {3}, đơn {4} {3})."
			).format(
				info["max_redeem_points"],
				info["loyalty_points"],
				info["conversion_factor"],
				invoice.currency,
				pre_total,
			)
		)

	invoice.apply_discount_on = "Grand Total"
	invoice.additional_discount_percentage = 0
	invoice.discount_amount = redeem * info["conversion_factor"]
	invoice.redeemed_points = redeem
	invoice.calculate_taxes_and_totals()
	# Gốc đổi điểm = Grand Total sau luật + phụ thu (dòng Actual). Không cho tổng âm.
	if flt(invoice.grand_total) < 0:
		frappe.throw(_("Số điểm đổi vượt tổng tiền đơn ({0} {1}).").format(pre_total, invoice.currency))

# ---------------------------------------------------------------------------
# API giao diện
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_pos_config(branch_name=None):
	"""Thông tin cấu hình cho giao diện: thương hiệu, POS Profile, phương thức thanh toán, quyền."""
	profile = _get_pos_profile(branch_name)
	roles = _pos_roles()

	return {
		"brand": get_brand_info(getattr(profile, "branch", None) or branch_name),
		"branch": getattr(profile, "branch", None),
		"profile": {
			"name": profile.name,
			"company": profile.company,
			"warehouse": profile.warehouse or "",
			"currency": profile.currency
			or frappe.db.get_value("Company", profile.company, "default_currency"),
			"customer": profile.customer or "",
			"selling_price_list": profile.get("selling_price_list") or "",
		},
		"payment_modes": _get_payment_modes(profile.company),
		"warnings": _company_warnings(profile),
		# Phân quyền màn POS (rỗng hết nếu user không có role POS -> frontend chặn).
		"roles": roles,
		"nav": _union_by_role(NAV_BY_ROLE, roles, NAV_ORDER),
		"kitchen_tabs": _kitchen_tabs(roles),
		"kitchen_transitions": [{"from": a, "to": b} for a, b in _kitchen_transitions(roles)],
		# Múi giờ site (System Settings): frontend so "Hôm nay/Hôm qua" theo múi này.
		"time_zone": get_system_timezone(),
		# Draft kênh khác QR tự hủy sau số phút này (order_cancel.POS_DRAFT_AUTO_CANCEL_MINUTES) — Orders hiện giờ tự hủy.
		"pos_draft_auto_cancel_minutes": _pos_draft_auto_cancel_minutes(),
	}


def _pos_draft_auto_cancel_minutes():
	from ..doctype.pos_invoice_hooks.order_cancel import POS_DRAFT_AUTO_CANCEL_MINUTES

	return POS_DRAFT_AUTO_CANCEL_MINUTES


@frappe.whitelist()
def get_menu_items(price_list=None):
	"""Danh sách menu (nhóm món) để hiển thị trên màn hình chọn món."""
	from ..doctype.mypos_menu.mypos_menu import MYPOSMenu

	return MYPOSMenu.get_menu_with_items(price_list=price_list)


@frappe.whitelist()
def get_buzzers(branch_name=None):
	"""Danh sách thẻ bàn kèm trạng thái thực tế cho popup chọn thẻ.

	status trả về tính theo đơn còn giữ ("Đang dùng" / "Sẵn sàng"), không theo field status lưu trên thẻ."""
	profile = _get_pos_profile(branch_name)
	branch = getattr(profile, "branch", None) or branch_name

	buzzers = frappe.get_all(
		"MYPOS Buzzer",
		filters={"branch": branch} if branch else {},
		fields=["name", "buzzer_number", "status", "branch"],
		order_by="buzzer_number asc",
	)

	# Thẻ đang bị đơn chưa kết thúc giữ (Draft hoặc đã thanh toán, pha chế chưa xong).
	held = _held_buzzers([b.name for b in buzzers]) if buzzers else {}

	for b in buzzers:
		b["used_by"] = held.get(b.name)
		b["available"] = b.name not in held
		b["status"] = "Đang dùng" if b["used_by"] else "Sẵn sàng"
	return buzzers

@frappe.whitelist()
def search_customers(query=None, limit=8):
	query = str(query or "").strip()
	if not query:
		return []

	digits = "".join(ch for ch in query if ch.isdigit())
	is_phone = len(digits) >= 3 and len(digits) >= len(query.replace(" ", "")) - 1

	if is_phone:
		or_filters = [["mobile_number", "like", f"%{digits}%"]]
	else:
		or_filters = [
			["customer_name", "like", f"%{query}%"],
			["mobile_number", "like", f"%{query}%"],
		]

	rows = frappe.get_all(
		"Customer",
		filters={"disabled": 0},
		or_filters=or_filters,
		fields=["name", "customer_name", "mobile_number"],
		order_by="modified desc",
		limit=min(int(limit), 20),
	)
	return [
		{"name": r.name, "customer_name": r.customer_name, "mobile_no": r.mobile_number}
		for r in rows
	]


@frappe.whitelist()
def get_customer_loyalty(customer, order_total=0):
	"""Điểm tích lũy của khách cho màn POS.

	Walk-in hoặc chưa có chương trình -> {"enrolled": False}.
	"""
	profile = _get_pos_profile()
	info = _loyalty_info(customer, profile.company, order_total)
	if not info:
		return {"enrolled": False}
	return {"enrolled": True, **info}


@frappe.whitelist()
def create_customer(customer_name, mobile_no=None):
	customer_name = str(customer_name or "").strip()
	mobile_no = "".join(ch for ch in str(mobile_no or "") if ch.isdigit() or ch == "+")

	if not customer_name:
		frappe.throw(_("Vui lòng nhập tên khách hàng."))
	if not mobile_no:
		frappe.throw(_("Vui lòng nhập số điện thoại để tránh nhầm khách trùng tên."))
	if frappe.db.exists("Customer", {"mobile_number": mobile_no}):
		frappe.throw(_("Số điện thoại {0} đã có khách hàng.").format(mobile_no))

	doc = frappe.new_doc("Customer")
	doc.customer_name = customer_name
	doc.customer_type = "Individual"
	doc.customer_group = (
		frappe.db.get_single_value("Selling Settings", "customer_group") or "Individual"
	)
	doc.territory = (
		frappe.db.get_single_value("Selling Settings", "territory") or "All Territories"
	)
	doc.mobile_number = mobile_no
	doc.insert(ignore_permissions=True)
	return {
		"name": doc.name,
		"customer_name": doc.customer_name,
		"mobile_no": doc.mobile_number,
	}

@frappe.whitelist()
def create_draft_order(
	items,
	order_type,
	customer_name=None,
	mode_of_payment=None,
	branch_name=None,
	price_list=None,
	order_note=None,
	buzzer=None,
	redeem_points=0,
):
	"""Tạo POS Invoice ở trạng thái Draft từ giỏ hàng.

	- Thanh toán tại quầy: đơn được tạo Draft, nhân viên thu tiền ở màn Orders.
	- Thanh toán QR: đơn được tạo Draft, sinh mã VietQR, webhook SePay sẽ submit.
	- redeem_points > 0: đổi điểm thành giảm giá trên Grand Total (xem _apply_redemption).
	- Pricing Rule (CTKM) do ERPNext tự áp; điểm đổi tối đa tính trên tổng SAU luật.
	"""
	_require_sale_role()
	rows = _normalize_items(items)
	if not rows:
		frappe.throw(_("Chưa chọn món nào để tạo đơn."))

	if order_type not in ORDER_TYPES:
		frappe.throw(_("Loại đơn không hợp lệ."))

	profile = _get_pos_profile(branch_name)
	mode = _resolve_mode_of_payment(profile.company, mode_of_payment)
	effective_price_list = _require_price_list(price_list)
	customer = _resolve_customer(customer_name)

	_ensure_opening_entry(profile)

	invoice = _build_invoice(profile, rows, order_type, customer, effective_price_list, mode, order_note)
	_apply_redemption(invoice, customer, profile.company, redeem_points)

	if order_type == "Dine In":
		invoice.buzzer = _assign_buzzer(profile, buzzer)

	try:
		invoice.insert(ignore_permissions=True)
	except Exception as exc:
		frappe.throw(_("Không tạo được đơn: {0}").format(str(exc)))

	invoice.reload()

	return {
		"invoice_name": invoice.name,
		"order_type": order_type,
		"grand_total": flt(invoice.grand_total),
		"amount": flt(invoice.rounded_total or invoice.grand_total),
		"currency": invoice.currency,
		"qty_sum": sum(flt(row.qty) for row in invoice.items),
		"buzzer_number": _buzzer_number(invoice.buzzer),
	}


@frappe.whitelist()
def preview_pricing(items, customer=None, price_list=None, redeem_points=0):
	"""Xem trước giá sau CTKM (Pricing Rule) và đổi điểm — dựng hóa đơn trong bộ nhớ, không ghi DB.

	Trả về từng dòng (giá gốc, giá sau luật, % giảm, số tiền tiết kiệm, luật áp dụng,
	cờ quà tặng) cùng các tổng và mức đổi điểm tối đa theo tổng sau luật.
	"""
	rows = _normalize_items(items)
	if not rows:
		frappe.throw(_("Chưa chọn món nào để tạo đơn."))

	profile = _get_pos_profile()
	mode = _resolve_mode_of_payment(profile.company, None)
	effective_price_list = _require_price_list(price_list)
	cust = _resolve_customer(customer)

	return _pricing_preview(profile, rows, cust, effective_price_list, mode, redeem_points)


def _pricing_preview(profile, rows, cust, effective_price_list, mode, redeem_points=0):
	"""Lõi của preview_pricing (dùng chung cho POS và web đặt món QR). Không ghi DB."""
	from erpnext.accounts.doctype.pricing_rule.utils import get_applied_pricing_rules

	invoice = _build_invoice(profile, rows, "Take Away", cust, effective_price_list, mode)
	after_rules = flt(invoice.grand_total)
	info = _loyalty_info(cust, profile.company, after_rules)
	_apply_redemption(invoice, cust, profile.company, redeem_points)

	rules_by_row = [get_applied_pricing_rules(row.get("pricing_rules")) for row in invoice.items]
	names = sorted({n for rules in rules_by_row for n in rules})
	titles = {}
	if names:
		titles = {
			r.name: r.title or r.name
			for r in frappe.get_all(
				"Pricing Rule", filters={"name": ["in", names]}, fields=["name", "title"]
			)
		}

	out_items, total_before = [], 0
	for row, rules in zip(invoice.items, rules_by_row):
		free = cint(row.get("is_free_item"))
		plr = flt(row.price_list_rate)
		rate = 0 if free else flt(row.rate)
		if not free:
			total_before += plr * flt(row.qty)
		out_items.append(
			{
				"item_code": row.item_code,
				"qty": flt(row.qty),
				"price_list_rate": plr,
				"rate": rate,
				"discount_percentage": flt(row.discount_percentage),
				"saved": (plr - rate) * flt(row.qty),
				"rules": [{"name": n, "title": titles.get(n, n)} for n in rules],
				"is_free_item": free,
			}
		)

	return {
		"items": out_items,
		"total_before": total_before,
		"total_discount_rules": total_before - flt(invoice.total),
		"loyalty_discount": flt(invoice.discount_amount),
		"total_surcharge": flt(_invoice_surcharge(invoice)),
		"grand_total": flt(invoice.grand_total),
		"max_redeem_points": info["max_redeem_points"] if info else 0,
	}


def _require_price_list(price_list):
	"""Price List bắt buộc — lấy từ menu đang chọn, không fallback sang POS Profile."""
	if not price_list:
		frappe.throw(_("Thiếu Price List của menu."))
	return str(price_list).strip()


def _build_invoice(profile, rows, order_type, customer, price_list, mode, order_note=""):
	"""Dựng POS Invoice trong bộ nhớ (CHƯA insert) và để ERPNext tự áp Pricing Rule.

	Không gán rate/price_list_rate: set_missing_values chỉ điền field đang trống.
	Vẫn chặn template và món chưa có giá trong Price List của menu.
	"""
	from ..doctype.mypos_menu.mypos_menu import MYPOSMenu

	invoice = _new_invoice_header(profile, order_type, customer, price_list, mode, order_note)

	for row in rows:
		row = dict(row)
		code = (
			row.get("item_code")
			or row.get("item")
			or row.get("name")
			or row.get("item_name")
			or row.get("id")
		)
		if not code or not frappe.db.exists("Item", code):
			frappe.throw(
				_("Không xác định được mã món từ dòng giỏ hàng: {0}").format(
					frappe.as_json(row)
				)
			)

		item = frappe.db.get_value(
			"Item",
			code,
			["stock_uom", "item_name", "has_variants", "variant_of"],
			as_dict=True,
		)
		if not item.stock_uom:
			frappe.throw(_("Món {0} chưa có đơn vị tính (Stock UOM).").format(code))

		# Template không được tạo đơn trực tiếp — bắt chọn size trước.
		if item.has_variants and not item.variant_of:
			frappe.throw(
				_("Món {0} cần chọn size.").format(item.item_name or code)
			)

		# Lấy rate từ Item Price theo ĐÚNG Price List của menu đang dùng.
		# Không fallback sang giá khác; không có thì throw nêu tên món và size.
		rate = MYPOSMenu.get_price_for_item(code, price_list)
		if rate is None:
			frappe.throw(
				_(
					"Món {0} ({1}) chưa có giá trong Price List của menu. "
					"Vui lòng chọn size đã có giá hoặc nhập giá trong Desk."
				).format(item.item_name or code, code)
			)

		row["item_code"] = code
		row["item_name"] = row.get("item_name") or item.item_name
		row["uom"] = item.stock_uom
		row["stock_uom"] = item.stock_uom
		row["conversion_factor"] = 1
		# Không gán rate/price_list_rate — ERPNext lấy giá theo Price List và áp CTKM.
		invoice.append("items", row)

	invoice.set_missing_values()
	# CTKM theo TỔNG qty mỗi mã trong hóa đơn (cùng món tách dòng vì khác tùy chọn).
	_apply_rules_on_total_qty(invoice, profile, order_type, customer, price_list, mode)
	invoice.calculate_taxes_and_totals()
	# Phụ thu tùy chọn món (topping): cộng SAU CTKM, một dòng Taxes and Charges kiểu Actual.
	_apply_option_surcharge(invoice, profile)
	return invoice


def _new_invoice_header(profile, order_type, customer, price_list, mode, order_note=""):
	"""POS Invoice mới (chưa có dòng) với header + thanh toán + Price List, bật Pricing Rule."""
	invoice = frappe.new_doc("POS Invoice")
	invoice.is_pos = 1
	invoice.pos_profile = profile.name
	invoice.customer = customer
	invoice.company = profile.company
	invoice.currency = profile.currency or frappe.db.get_value(
		"Company", profile.company, "default_currency"
	)
	invoice.transaction_date = nowdate()
	invoice.posting_date = nowdate()
	invoice.set_warehouse = profile.warehouse or ""
	invoice.order_type = order_type
	invoice.order_channel = ORDER_CHANNEL

	invoice.order_note = str(order_note or "").strip()[:500]

	# Phương thức thanh toán do nhân viên chọn — set sẵn để ERPNext không
	# ghi đè bằng danh sách MoP của POS Profile.
	invoice.set("payments", [])
	invoice.append(
		"payments",
		{
			"mode_of_payment": mode["name"],
			"amount": 0,
			"account": mode["account"],
			"type": mode["type"],
		},
	)

	# Giá theo đúng Price List của menu; bật Pricing Rule (CTKM).
	invoice.selling_price_list = price_list
	invoice.ignore_pricing_rule = 0
	return invoice


# Field giá/luật chép từ dòng tạm (qty tổng) sang các dòng thật cùng mã.
_RULE_FIELDS = (
	"pricing_rules", "discount_percentage", "discount_amount", "rate",
	"margin_type", "margin_rate_or_amount", "rate_with_margin",
)


# ---------------------------------------------------------------------------
# Phụ thu tùy chọn món (MYPOS Option Value.extra_price) — 2026-11-17
# ---------------------------------------------------------------------------
# Nhận diện dòng phụ thu trong bảng taxes: charge_type Actual + mô tả cố định (không thêm Custom Field).
SURCHARGE_DESCRIPTION = "Phụ thu tùy chọn món"


def _invoice_surcharge(invoice):
	"""Tổng phụ thu = Σ qty × phụ thu mỗi đơn vị (snapshot trong JSON options), bỏ dòng tặng."""
	from ..doctype.mypos_option_group.option_resolver import line_surcharge

	return sum(
		flt(row.qty) * line_surcharge(row.get("options"))
		for row in invoice.items
		if not cint(row.get("is_free_item"))
	)


def _is_surcharge_row(tax):
	return tax.charge_type == "Actual" and (tax.description or "") == SURCHARGE_DESCRIPTION


def _surcharge_account(profile):
	"""Tài khoản doanh thu cho dòng phụ thu: POS Profile.income_account -> Company.default_income_account."""
	account = profile.get("income_account") or frappe.db.get_value(
		"Company", profile.company, "default_income_account"
	)
	if not account:
		frappe.throw(
			_(
				"Chưa cấu hình tài khoản doanh thu cho phụ thu tùy chọn món: điền Income Account ở POS Profile {0} "
				"hoặc Default Income Account của công ty {1}."
			).format(profile.name, profile.company)
		)
	return account


def _apply_option_surcharge(invoice, profile):
	"""Cộng phụ thu tùy chọn món vào ĐÚNG MỘT dòng Taxes and Charges kiểu Actual (sau CTKM).

	- Idempotent: gọi nhiều lần không nhân đôi (luôn tính lại từ JSON options, cập nhật dòng cũ).
	- Tổng = 0 -> xóa dòng phụ thu cũ nếu có (đơn không topping có giá: số liệu như trước).
	- Dòng Actual không chịu thuế % của mẫu thuế; không bị Pricing Rule giảm; Grand Total gồm phụ thu
	  nên đổi điểm (giảm trên Grand Total) tính trên tổng sau luật + phụ thu.
	- ERPNext không tính lại số tiền của dòng Actual khi save/submit, nên phụ thu không bị ghi đè.
	"""
	total = flt(_invoice_surcharge(invoice), invoice.precision("grand_total"))
	others = [t for t in invoice.get("taxes") or [] if not _is_surcharge_row(t)]
	existing = [t for t in invoice.get("taxes") or [] if _is_surcharge_row(t)]

	if total <= 0:
		if existing:
			invoice.set("taxes", others)
			for i, t in enumerate(invoice.taxes, 1):
				t.idx = i
			invoice.calculate_taxes_and_totals()
		return

	row = existing[0] if existing else None
	if row is None:
		row = invoice.append("taxes", {"charge_type": "Actual", "description": SURCHARGE_DESCRIPTION})
	row.account_head = _surcharge_account(profile)
	row.cost_center = row.cost_center or profile.get("cost_center") or frappe.db.get_value(
		"Company", profile.company, "cost_center"
	)
	row.rate = 0
	row.included_in_print_rate = 0
	row.tax_amount = total
	if len(existing) > 1:  # dọn bản trùng (nếu có) — giữ một dòng
		invoice.set("taxes", others + [row])
	for i, t in enumerate(invoice.taxes, 1):
		t.idx = i
	invoice.calculate_taxes_and_totals()


def _apply_rules_on_total_qty(invoice, profile, order_type, customer, price_list, mode):
	"""Áp Pricing Rule theo TỔNG qty của mỗi item_code trong hóa đơn.

	ERPNext xét qty của luật theo TỪNG DÒNG; cùng món tách dòng (khác tùy chọn) như 2+2 ly
	sẽ chỉ được mức giảm của qty 2. Cách làm: với mã có >= 2 dòng (không tính dòng tặng),
	dựng hóa đơn tạm trong bộ nhớ, mỗi mã một dòng qty = tổng, để ERPNext tự chọn luật,
	rồi chép kết quả sang mọi dòng thật cùng mã. Luật vẫn tính theo từng mã (không cộng chéo).

	KHÔNG dùng Pricing Rule.is_cumulative (cộng qty qua các hóa đơn trước) hay mixed_conditions
	(cộng chéo giữa các mã). Luật tặng sản phẩm (Product) không gộp: giữ theo từng dòng.
	"""
	from erpnext.accounts.doctype.pricing_rule.utils import get_applied_pricing_rules

	by_code = {}
	for row in invoice.items:
		if not cint(row.get("is_free_item")):
			by_code.setdefault(row.item_code, []).append(row)
	multi = {code: rows for code, rows in by_code.items() if len(rows) > 1}
	if not multi:
		return

	temp = _new_invoice_header(profile, order_type, customer, price_list, mode)
	for code, rows in multi.items():
		first = rows[0]
		temp.append(
			"items",
			{
				"item_code": code,
				"item_name": first.item_name,
				"qty": sum(flt(r.qty) for r in rows),
				"uom": first.uom,
				"stock_uom": first.stock_uom,
				"conversion_factor": first.conversion_factor or 1,
			},
		)
	temp.set_missing_values()

	for t in temp.items:
		if cint(t.get("is_free_item")) or t.item_code not in multi:
			continue
		rules = get_applied_pricing_rules(t.get("pricing_rules"))
		kinds = {
			frappe.db.get_value("Pricing Rule", r, "price_or_product_discount") for r in rules
		}
		if "Product" in kinds:
			frappe.log_error(
				title="Leescoffee POS: CTKM tặng sản phẩm không gộp qty",
				message=f"{t.item_code}: luật {rules} là tặng sản phẩm, giữ áp theo từng dòng.",
			)
			continue
		for row in multi[t.item_code]:
			if rules:
				for field in _RULE_FIELDS:
					row.set(field, t.get(field))
			else:
				row.pricing_rules = ""
				row.discount_percentage = 0
				row.discount_amount = 0
				row.rate = flt(row.price_list_rate)


# ---------------------------------------------------------------------------
# Màn Đơn hàng (Orders): "Ca hiện tại" (mặc định) và "Lịch sử" (chỉ MANAGER)
# ---------------------------------------------------------------------------
# POS Invoice không có link tới POS Opening Entry. ERPNext chỉ cho mỗi POS Profile 1 ca Open
# (sales_invoice.validate_pos_opening_entry) và đóng ca gom đơn theo
# Timestamp(posting_date, posting_time) >= period_start_date (pos_closing_entry.build_invoice_query)
# -> đơn thuộc ca hiện tại = cùng POS Profile + Timestamp >= period_start_date của ca Open.
ORDERS_MAX_LIMIT = 200
HISTORY_MAX_DAYS = 31
HISTORY_STATUSES = ("Paid", "Consolidated")
ORDER_SCOPES = ("shift", "history")
ORDER_LIST_FIELDS = (
	"name",
	"customer",
	"customer_name",
	"order_type",
	"order_channel",
	"status",
	"docstatus",
	"grand_total",
	"rounded_total",
	"currency",
	"payment_status",
	"payment_code",
	"custom_kitchen_status",
	"buzzer",
	"creation",
)


def _order_scope(scope, roles=None):
	"""Kiểm tra scope; "history" chỉ dành cho MANAGER (gồm System Manager / Administrator)."""
	scope = scope or "shift"
	if scope not in ORDER_SCOPES:
		frappe.throw(_("Chế độ xem đơn không hợp lệ."))
	if scope == "history" and not (roles or _pos_roles())["manager"]:
		frappe.throw(_("Chỉ quản lý (POS MANAGER) được xem lịch sử đơn."), frappe.PermissionError)
	return scope


def _open_shift_of(profile_name):
	"""Ca POS đang mở của POS Profile (bất kỳ thu ngân), không có -> None. Không tự mở ca."""
	rows = frappe.get_all(
		"POS Opening Entry",
		filters={"pos_profile": profile_name, "status": "Open", "docstatus": 1},
		fields=["name", "period_start_date"],
		order_by="period_start_date desc",
		limit=1,
	)
	return rows[0] if rows else None


def _history_range(from_date=None, to_date=None):
	"""[from, to] của Lịch sử: mặc định hôm qua; from <= to; tối đa HISTORY_MAX_DAYS ngày."""
	yesterday = add_days(nowdate(), -1)
	try:
		start = getdate(from_date or yesterday)
		end = getdate(to_date or from_date or yesterday)
	except Exception:
		frappe.throw(_("Ngày lọc không hợp lệ."))
	if start > end:
		frappe.throw(_("Ngày bắt đầu phải trước hoặc bằng ngày kết thúc."))
	if (end - start).days + 1 > HISTORY_MAX_DAYS:
		frappe.throw(_("Chỉ xem được tối đa {0} ngày mỗi lần.").format(HISTORY_MAX_DAYS))
	return start, end


def _like(text):
	"""Mẫu LIKE chứa `text` (thoát ký tự đặc biệt)."""
	text = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
	return f"%{text}%"


def _order_conditions(invoice, profile_name, scope, status, shift, from_date=None, to_date=None, search=None):
	"""Điều kiện frappe.qb cho danh sách đơn Orders. None = chắc chắn rỗng (ca hiện tại khi chưa mở ca)."""
	from frappe.query_builder import functions as fn

	cond = (invoice.pos_profile == profile_name) & (invoice.is_return == 0)
	if scope == "history":
		start, end = _history_range(from_date, to_date)
		cond &= (
			(invoice.docstatus == 1)
			& invoice.status.isin(HISTORY_STATUSES)
			& invoice.posting_date.between(start, end)
		)
	else:
		if not shift:
			return None
		cond &= fn.Timestamp(invoice.posting_date, invoice.posting_time) >= shift.period_start_date
		draft = invoice.docstatus == 0
		paid = (invoice.docstatus == 1) & (invoice.status == "Paid")
		if status == "draft":
			cond &= draft
		elif status == "paid":
			cond &= paid
		else:
			cond &= draft | paid

	query = (search or "").strip().lstrip("#").strip()[:100]
	if query:
		pattern = _like(query)
		cond &= invoice.name.like(pattern) | invoice.customer_name.like(pattern)
	return cond


def _count(invoice, cond):
	from frappe.query_builder.functions import Count

	if cond is None:
		return 0
	return cint(frappe.qb.from_(invoice).select(Count("*")).where(cond).run()[0][0])


@frappe.whitelist()
def get_orders(status="all", limit=50, scope="shift", from_date=None, to_date=None, search=None, start=0):
	"""Danh sách đơn cho màn hình Orders (của POS Profile hiện tại).

	status: "all" | "draft" | "paid" (scope "shift").
	scope:
	- "shift" (mặc định): đơn Draft + Paid của ca đang mở; chưa mở ca -> [].
	- "history" (chỉ MANAGER): đơn Paid + Consolidated có posting_date trong [from_date, to_date]
	  (mặc định hôm qua, tối đa HISTORY_MAX_DAYS ngày); bỏ qua `status`.
	search: khớp mã đơn / tên khách. limit <= ORDERS_MAX_LIMIT, start = vị trí bắt đầu ("Xem thêm").
	Mỗi dòng giữ nguyên khóa cũ (+ amount, buzzer_number).
	"""
	from frappe.query_builder import DocType, Order

	_require_sale_role()
	scope = _order_scope(scope)
	profile_name = resolve_pos_profile_name()
	shift = _open_shift_of(profile_name) if scope == "shift" else None

	invoice = DocType("POS Invoice")
	cond = _order_conditions(invoice, profile_name, scope, status, shift, from_date, to_date, search)
	if cond is None:
		return []

	limit = min(max(cint(limit) or 50, 1), ORDERS_MAX_LIMIT)
	orders = (
		frappe.qb.from_(invoice)
		.select(*[invoice[f] for f in ORDER_LIST_FIELDS])
		.where(cond)
		.orderby(invoice.creation, order=Order.desc)
		.orderby(invoice.name, order=Order.desc)
		.limit(limit)
		.offset(max(cint(start), 0))
		.run(as_dict=True)
	)

	for order in orders:
		order["amount"] = flt(order.get("rounded_total") or order.get("grand_total"))
		order["buzzer_number"] = _buzzer_number(order.get("buzzer"))

	return orders


@frappe.whitelist()
def get_orders_summary(scope="shift", from_date=None, to_date=None, search=None):
	"""Bộ đếm + thông tin ca cho màn Orders (COUNT cùng bộ lọc với get_orders).

	Trả {scope, shift: {name, period_start_date} | None, counts: {draft, paid}, old_drafts,
	from_date, to_date}. old_drafts = đơn Draft của POS Profile thuộc ca trước (trước giờ mở ca
	hiện tại, hoặc mọi Draft khi chưa mở ca) — chỉ tính cho MANAGER, role khác = 0.
	"""
	from frappe.query_builder import DocType
	from frappe.query_builder import functions as fn

	_require_sale_role()
	roles = _pos_roles()
	scope = _order_scope(scope, roles)
	profile_name = resolve_pos_profile_name()
	shift = _open_shift_of(profile_name)
	invoice = DocType("POS Invoice")

	def count(status):
		return _count(
			invoice,
			_order_conditions(invoice, profile_name, scope, status, shift, from_date, to_date, search),
		)

	result = {
		"scope": scope,
		"shift": {"name": shift.name, "period_start_date": str(shift.period_start_date)} if shift else None,
		"from_date": None,
		"to_date": None,
	}
	if scope == "history":
		start, end = _history_range(from_date, to_date)
		result.update(from_date=str(start), to_date=str(end))
		result["counts"] = {"draft": 0, "paid": count("paid")}
	else:
		result["counts"] = {"draft": count("draft"), "paid": count("paid")}

	old_drafts = 0
	if roles["manager"]:
		cond = (invoice.pos_profile == profile_name) & (invoice.docstatus == 0) & (invoice.is_return == 0)
		if shift:
			cond &= fn.Timestamp(invoice.posting_date, invoice.posting_time) < shift.period_start_date
		old_drafts = _count(invoice, cond)
	result["old_drafts"] = old_drafts
	return result


@frappe.whitelist()
def get_order_detail(invoice_name):
	"""Chi tiết một đơn (món, tổng tiền, thanh toán, trạng thái bếp, thẻ bàn, CTKM)."""
	from erpnext.accounts.doctype.pricing_rule.utils import get_applied_pricing_rules

	from ..doctype.mypos_option_group.option_resolver import read_line_options

	invoice = frappe.get_doc("POS Invoice", invoice_name)
	sizes = _size_labels([row.item_code for row in invoice.items])

	items = [
		{
			"item_code": row.item_code,
			"item_name": row.item_name,
			"qty": flt(row.qty),
			"rate": flt(row.rate),
			"amount": flt(row.amount),
			"sugar_level": row.get("sugar_level") or "",
			"ice_level": row.get("ice_level") or "",
			"options": read_line_options(row.get("options"), row.get("sugar_level"), row.get("ice_level")),
			"size": sizes.get(row.item_code, ""),
			"price_list_rate": flt(row.price_list_rate),
			"discount_percentage": flt(row.discount_percentage),
			"pricing_rules": get_applied_pricing_rules(row.get("pricing_rules")),
		}
		for row in invoice.items
	]

	payments = [
		{
			"mode_of_payment": row.mode_of_payment,
			"amount": flt(row.amount),
			"type": row.type,
			"account": row.account,
		}
		for row in invoice.payments
	]

	return {
		"name": invoice.name,
		"customer": invoice.customer,
		"customer_name": invoice.customer_name or invoice.customer,
		"order_type": invoice.order_type,
		"order_channel": invoice.order_channel,
		"status": invoice.status,
		"docstatus": invoice.docstatus,
		"payment_status": invoice.payment_status,
		"payment_code": invoice.payment_code or "",
		"custom_kitchen_status": invoice.custom_kitchen_status or "",
		# Người/giờ từng bước + kết thúc có lý do (2026-11-20, kitchen_status.py).
		"kitchen_done_by": invoice.get("kitchen_done_by") or "",
		"kitchen_done_at": invoice.get("kitchen_done_at"),
		"kitchen_completed_by": invoice.get("kitchen_completed_by") or "",
		"kitchen_completed_at": invoice.get("kitchen_completed_at"),
		"kitchen_outcome_reason": invoice.get("kitchen_outcome_reason") or "",
		"cancel_reason": invoice.get("custom_cancel_reason") or "",
		"buzzer": invoice.buzzer,
		"buzzer_number": _buzzer_number(invoice.buzzer),
		"grand_total": flt(invoice.grand_total),
		"amount": flt(invoice.rounded_total or invoice.grand_total),
		"currency": invoice.currency,
		"items": items,
		"payments": payments,
		"creation": invoice.creation,
		"order_note": invoice.get("order_note") or "",
		"discount_amount": flt(invoice.discount_amount),
		"redeemed_points": int(flt(invoice.get("redeemed_points"))),
		# Phụ thu tùy chọn món đã lưu trên hóa đơn (dòng Taxes and Charges kiểu Actual).
		"total_surcharge": flt(sum(flt(t.tax_amount) for t in invoice.get("taxes") or [] if _is_surcharge_row(t))),
	}


@frappe.whitelist()
def pay_cash(invoice_name):
	"""Thu tiền tại quầy: đặt đúng số tiền của đơn rồi submit."""
	_require_sale_role()
	invoice = frappe.get_doc("POS Invoice", invoice_name)

	if invoice.docstatus != 0:
		frappe.throw(_("Đơn {0} không ở trạng thái Draft.").format(invoice_name))

	if not invoice.payments:
		frappe.throw(_("Đơn chưa có phương thức thanh toán."))

	amount = flt(invoice.rounded_total or invoice.grand_total)

	for payment in invoice.payments:
		payment.amount = amount

	invoice.save(ignore_permissions=True)
	invoice.submit()
	invoice.reload()

	return {
		"invoice_name": invoice.name,
		"status": invoice.status,
		"payment_status": invoice.payment_status,
		"amount": amount,
		"currency": invoice.currency,
	}

@frappe.whitelist()
def cancel_draft_order(invoice_name, force=0, reason=None, note=None):
	"""Hủy đơn Draft chưa thanh toán: đơn chuyển Cancelled, lý do lưu ở custom_cancel_reason (order_cancel.cancel_draft).

	Dùng chung cho màn Orders (/pos) và nút "Hủy đơn" trên form POS Invoice (Desk, quản lý).
	- Chỉ cho docstatus = 0. Đơn đã thanh toán không hủy được tại POS.
	- Đơn đã sinh QR (đang chờ chuyển khoản) cần force=1 để tránh hủy nhầm
	  đơn khách đã chuyển tiền.
	- Thẻ bàn tự được nhả vì _assign_buzzer / get_buzzers chỉ xét đơn docstatus 0/1.
	- reason: phải thuộc order_cancel.MANUAL_REASONS, "Khác" bắt buộc note.
	  reason=None (giao diện cũ chưa gửi) -> vẫn hủy, lý do REASON_LEGACY.
	"""
	from ..doctype.pos_invoice_hooks import order_cancel as OC

	_require_sale_role()
	if reason is None:
		reason = OC.REASON_LEGACY
	else:
		reason = str(reason).strip()
		if reason not in OC.MANUAL_REASONS:
			frappe.throw(_("Chọn lý do hủy đơn: {0}.").format(", ".join(OC.MANUAL_REASONS)))
		if reason == OC.REASON_OTHER and not (note or "").strip():
			frappe.throw(_("Lý do \"Khác\": nhập ghi chú."))
	invoice = frappe.get_doc("POS Invoice", invoice_name)

	if invoice.docstatus != 0:
		frappe.throw(_("Đơn {0} đã thanh toán, không thể hủy tại POS.").format(invoice_name))

	if (invoice.get("payment_status") or "") == "Đang chờ" and not int(force or 0):
		frappe.throw(
			_(
				"Đơn {0} đã sinh mã QR và đang chờ thanh toán. "
				"Hãy chắc chắn khách chưa chuyển tiền trước khi hủy."
			).format(invoice_name)
		)

	buzzer_number = _buzzer_number(invoice.buzzer)
	result = OC.cancel_draft(invoice_name, reason, OC.SOURCE_MANUAL, note=note)

	return {
		"invoice_name": invoice_name,
		"buzzer_number": buzzer_number,
		"cancel_reason": result["cancel_reason"],
		"message": _("Đã hủy đơn {0}.").format(invoice_name),
	}


@frappe.whitelist()
def generate_qr(invoice_name):
	"""Sinh mã VietQR cho đơn (idempotent — gọi lại trả về mã cũ)."""
	from ..doctype.sepay.sepay import generate_qr_for_invoice

	return generate_qr_for_invoice(invoice_name)


@frappe.whitelist()
def confirm_pickup(invoice_name):
	"""Dự phòng: trả thẻ bàn về Sẵn sàng khi đơn đã kết thúc (frontend không còn nút; _resolve_consolidated vẫn dùng hook)."""
	from ..doctype.pos_invoice_hooks.pos_invoice_hooks import PosInvoiceHooks

	invoice = frappe.get_doc("POS Invoice", invoice_name)

	PosInvoiceHooks.confirm_pickup(invoice, method="confirm_pickup")

	return {
		"invoice_name": invoice.name,
		"buzzer_number": _buzzer_number(invoice.buzzer),
		"message": _("Đã xác nhận khách lấy món."),
	}


SERVE_QUEUE_LIMIT = 50
SERVE_PREVIEW_ITEMS = 2


@frappe.whitelist()
def get_serve_queue():
	"""Hàng chờ phục vụ cho thu ngân (2026-11-23): đơn tại quầy (kênh khác QR) đã thanh toán, pha chế "Đã làm",
	của POS Profile hiện tại — đơn cũ nhất trước.

	Dine In: phục vụ mang tới thẻ bàn; Take Away: gọi khách lấy. Đơn QR không vào (khách tự tới quầy, luồng QR không đổi).
	Chặn KITCHEN (_require_sale_role). Không gửi chéo chi nhánh: lọc theo resolve_pos_profile_name() của người gọi.
	Mỗi đơn: name, order_type, buzzer_number, customer_name ("" nếu Walk-in), item_count, items_preview,
	done_at, waiting_seconds (tính ở server, không phụ thuộc đồng hồ máy quầy).
	"""
	from frappe.utils import get_datetime, time_diff_in_seconds

	from ..doctype.pos_invoice_hooks.kitchen_status import KS_PREPARED

	_require_sale_role()
	profile_name = resolve_pos_profile_name()
	rows = frappe.get_all(
		"POS Invoice",
		filters={
			"pos_profile": profile_name,
			"docstatus": 1,
			"status": "Paid",
			"is_return": 0,
			"custom_kitchen_status": KS_PREPARED,
			"order_channel": ["!=", "QR"],
		},
		fields=["name", "order_type", "customer", "customer_name", "buzzer", "kitchen_done_at", "creation"],
		order_by="creation asc",
		limit=SERVE_QUEUE_LIMIT,
	)
	if not rows:
		return []

	names = [r.name for r in rows]
	items = {}
	for it in frappe.get_all(
		"POS Invoice Item",
		filters={"parent": ["in", names], "parenttype": "POS Invoice"},
		fields=["parent", "item_name", "qty"],
		order_by="parent asc, idx asc",
	):
		items.setdefault(it.parent, []).append(it)

	buzzers = {r.buzzer for r in rows if r.buzzer}
	numbers = dict(frappe.get_all("MYPOS Buzzer", filters={"name": ["in", list(buzzers)]},
		fields=["name", "buzzer_number"], as_list=True)) if buzzers else {}

	now = now_datetime()
	result = []
	for r in rows:
		lines = items.get(r.name, [])
		done_at = r.kitchen_done_at or r.creation
		result.append({
			"name": r.name,
			"order_type": r.order_type,
			"buzzer_number": numbers.get(r.buzzer) if r.buzzer else None,
			"customer_name": "" if r.customer == WALK_IN else (r.customer_name or r.customer or ""),
			"item_count": int(sum(flt(x.qty) for x in lines)),
			"items_preview": [f"{x.item_name} x{int(flt(x.qty))}" for x in lines[:SERVE_PREVIEW_ITEMS]],
			"more_lines": max(len(lines) - SERVE_PREVIEW_ITEMS, 0),
			"done_at": str(done_at) if done_at else None,
			"waiting_seconds": max(int(time_diff_in_seconds(now, get_datetime(done_at))), 0) if done_at else 0,
		})
	# Cũ nhất (theo giờ "Đã làm") trước.
	result.sort(key=lambda o: -o["waiting_seconds"])
	return result


@frappe.whitelist()
def get_status_board():
	"""Bảng trạng thái bếp (đơn đã thanh toán, đang làm / hoàn thành)."""
	from ..doctype.pos_invoice_hooks.pos_invoice_hooks import get_status_board_orders

	return get_status_board_orders()

@frappe.whitelist()
def get_kitchen_orders(status=None, limit=100):
	"""Đơn đã thanh toán cho màn pha chế, đơn cũ nhất lên đầu.

	Chỉ trả trạng thái nằm trong KITCHEN_TABS_BY_ROLE của user. "Đã hoàn thành" chỉ lấy
	đơn posting_date = hôm nay (Chưa làm / Đã làm lấy mọi ngày).
	"""
	roles = _pos_roles()
	_require_pos_role(roles)
	allowed = _kitchen_tabs(roles)

	if status:
		if status not in KITCHEN_FLOW:
			frappe.throw(_("Trạng thái không hợp lệ."))
		if status not in allowed:
			frappe.throw(
				_("Bạn không có quyền xem đơn ở trạng thái '{0}'.").format(status),
				frappe.PermissionError,
			)
		statuses = [status]
	else:
		statuses = allowed

	if not statuses:
		return []

	fields = ["name", "customer", "customer_name", "order_type", "order_channel",
		"custom_kitchen_status", "buzzer", "order_note", "creation", "modified"]
	base = {"docstatus": 1, "status": "Paid"}
	cap = min(int(limit), 200)

	orders = []
	open_statuses = [s for s in statuses if s != "Đã hoàn thành"]
	if open_statuses:
		orders += frappe.get_all(
			"POS Invoice",
			filters={**base, "custom_kitchen_status": ["in", open_statuses]},
			fields=fields,
			order_by="creation asc",
			limit=cap,
		)
	if "Đã hoàn thành" in statuses:
		orders += frappe.get_all(
			"POS Invoice",
			filters={**base, "custom_kitchen_status": "Đã hoàn thành", "posting_date": nowdate()},
			fields=fields,
			order_by="creation asc",
			limit=cap,
		)
	if not orders:
		return []
	orders.sort(key=lambda o: o.creation)

	names = [o.name for o in orders]
	rows = frappe.get_all(
		"POS Invoice Item",
		filters={"parent": ["in", names], "parenttype": "POS Invoice"},
		fields=["parent", "idx", "item_code", "item_name", "qty",
			"sugar_level", "ice_level", "options"],
		order_by="parent asc, idx asc",
	)
	from ..doctype.mypos_option_group.option_resolver import read_line_options

	by_parent = {}
	for r in rows:
		by_parent.setdefault(r.parent, []).append({
			"item_code": r.item_code,
			"item_name": r.item_name,
			"qty": flt(r.qty),
			"sugar_level": r.sugar_level or "",
			"ice_level": r.ice_level or "",
			"options": read_line_options(r.get("options"), r.sugar_level, r.ice_level),
		})

	for o in orders:
		o["kitchen_status"] = o.pop("custom_kitchen_status")
		o["items"] = by_parent.get(o.name, [])
		o["buzzer_number"] = _buzzer_number(o.get("buzzer"))
		o["customer_name"] = o.get("customer_name") or o.get("customer")
	return orders


@frappe.whitelist()
def set_kitchen_status(invoice_name, status):
	"""Đổi trạng thái pha chế, chỉ cho đi tiến từng bước, đúng bước role được phép."""
	roles = _pos_roles()
	_require_pos_role(roles)
	if status not in KITCHEN_FLOW:
		frappe.throw(_("Trạng thái không hợp lệ."))

	invoice = frappe.get_doc("POS Invoice", invoice_name)
	if invoice.docstatus != 1 or invoice.status != "Paid":
		frappe.throw(_("Đơn {0} chưa thanh toán.").format(invoice_name))

	current = invoice.custom_kitchen_status or "Chưa làm"
	if current not in KITCHEN_FLOW or (current == KITCHEN_FLOW[-1] and current != status):
		frappe.throw(_("Đơn {0} đã kết thúc ({1}), không đổi trạng thái pha chế được.").format(invoice_name, current))
	if KITCHEN_FLOW.index(status) != KITCHEN_FLOW.index(current) + 1:
		frappe.throw(
			_("Không thể chuyển {0} từ '{1}' sang '{2}'.").format(invoice_name, current, status)
		)

	if (current, status) not in _kitchen_transitions(roles):
		frappe.throw(
			_("Vai trò của bạn không được chuyển đơn từ '{0}' sang '{1}'.").format(current, status),
			frappe.PermissionError,
		)

	invoice.custom_kitchen_status = status
	# Người/giờ từng bước (2026-11-20).
	if status == KITCHEN_FLOW[1]:
		invoice.kitchen_done_by = frappe.session.user
		invoice.kitchen_done_at = now_datetime()
	elif status == KITCHEN_FLOW[-1]:
		invoice.kitchen_completed_by = frappe.session.user
		invoice.kitchen_completed_at = now_datetime()
	invoice.save(ignore_permissions=True)  # hook on_update_after_submit tự nhả thẻ bàn
	return {"invoice_name": invoice.name, "kitchen_status": status}


def _resolve_consolidated(invoice, outcome, text):
	"""Đơn đã gộp khi đóng ca (Consolidated) mà còn Chưa làm / Đã làm (dữ liệu cũ): quản lý kết thúc bằng db_set —
	không save() lại hóa đơn đã gộp. Thẻ bàn: nhả nếu không còn đơn khác giữ."""
	from ..doctype.pos_invoice_hooks import kitchen_status as KS

	if not _pos_roles()["manager"]:
		frappe.throw(_("Đơn {0} đã gộp khi đóng ca: chỉ quản lý (POS MANAGER) được xử lý.").format(invoice.name), frappe.PermissionError)
	previous = invoice.custom_kitchen_status or KS.KS_TODO
	actor = frappe.session.user
	invoice.db_set(
		{
			"custom_kitchen_status": outcome,
			"kitchen_completed_by": actor,
			"kitchen_completed_at": now_datetime(),
			"kitchen_outcome_reason": text,
		},
		update_modified=True,
	)
	invoice.add_comment(
		"Info", _("Kết thúc đơn: {0} → {1}. Lý do: {2}. Bởi {3}.").format(previous, outcome, text, actor)
	)
	# db_set không chạy hook on_update_after_submit (hook đó cũng chỉ xét đơn Paid) -> nhả thẻ bằng confirm_pickup.
	from ..doctype.pos_invoice_hooks.pos_invoice_hooks import PosInvoiceHooks

	PosInvoiceHooks.confirm_pickup(invoice, method="resolve_open_order")


def _resolve_open_order(invoice_name, outcome, reason=None, note=None):
	"""Kết thúc MỘT đơn dở (đã thanh toán, đang Chưa làm / Đã làm) với kết quả + lý do (kitchen_status.set_terminal).

	Không có xử lý hàng loạt: mỗi đơn một lý do (Van chốt 2026-11-23).
	"""
	from ..doctype.pos_invoice_hooks import kitchen_status as KS

	if outcome not in KS.RESOLVE_OUTCOMES:
		frappe.throw(_("Kết quả không hợp lệ. Chọn: {0}.").format(", ".join(KS.RESOLVE_OUTCOMES)))
	invoice = frappe.get_doc("POS Invoice", invoice_name)
	if invoice.docstatus != 1 or cint(invoice.get("is_return")) or invoice.status not in ("Paid", "Consolidated"):
		frappe.throw(_("Đơn {0} chưa thanh toán hoặc không phải đơn bán.").format(invoice_name))
	current = invoice.custom_kitchen_status or KS.KS_TODO
	if current not in KS.KITCHEN_BLOCK_STATUSES:
		frappe.throw(_("Đơn {0} đã kết thúc ({1}).").format(invoice_name, current))
	reason = (reason or "").strip()
	# Giao bình thường (Đã làm -> Đã hoàn thành) không cần lý do; mọi trường hợp khác bắt buộc.
	if not (outcome == KS.KS_COMPLETED and current == KS.KS_PREPARED) and not reason:
		frappe.throw(_("Nhập lý do khi chuyển đơn {0} từ '{1}' sang '{2}'.").format(invoice_name, current, outcome))
	if invoice.status == "Consolidated":
		text = "; ".join(x.strip() for x in (reason, note or "") if x and x.strip())
		if not text:
			frappe.throw(_("Nhập lý do khi xử lý đơn {0}.").format(invoice_name))
		_resolve_consolidated(invoice, outcome, text)
	else:
		KS.set_terminal(invoice, outcome, reason, note)
	return {
		"invoice_name": invoice.name,
		"kitchen_status": outcome,
		"buzzer_number": _buzzer_number(invoice.buzzer),
	}


@frappe.whitelist()
def resolve_open_order(invoice_name, outcome, reason=None, note=None):
	"""Thu ngân / quản lý kết thúc một đơn dở: "Đã hoàn thành", "Khách không nhận", "Không thực hiện được".

	Lý do bắt buộc trừ "Đã hoàn thành" từ "Đã làm". Ghi người/giờ, lý do (kitchen_outcome_reason), comment; nhả thẻ bàn.
	Dùng bởi nút "Xử lý đơn" trên form POS Invoice (Desk, quản lý).
	"""
	_require_sale_role()
	return _resolve_open_order(invoice_name, outcome, reason, note)
