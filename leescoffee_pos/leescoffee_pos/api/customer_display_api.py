"""Màn hình khách (/pos/customer) — chỉ hiển thị, đăng nhập bằng tài khoản thu ngân.

Trạng thái hiển thị lưu ở Redis cache theo user (`mypos_cdisplay:<user>`), server là nguồn sự thật:

    {v, phase: idle|cart|order|qr|paid, pos_profile, invoice?, cart?, qr?, paid_at?}

- cart  : preview_pricing(display=1) lưu kết quả đã tính (tiền KHÔNG lấy từ client).
- order : create_draft_order, hoặc thu ngân chọn đơn Draft ở Orders (set_customer_display).
- qr    : pos_api.generate_qr.
- paid  : hook on_submit của POS Invoice khi status = Paid (tiền mặt / webhook SePay).
- idle  : giỏ rỗng, hủy đơn (order_cancel.cancel_draft).

Mỗi lần ghi: v = mốc thời gian (ms) + publish_realtime tới đúng user; màn khách gọi
get_customer_display_state(since=v) để lấy dữ liệu (poll dự phòng khi socket không chạy).
Mọi điểm móc từ luồng bán hàng đi qua _safe(): lỗi hiển thị không bao giờ chặn bán hàng / thanh toán.
"""

import time

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from ..doctype.branch_config.branch_config import get_brand_info, resolve_pos_profile_name
from ..doctype.pos_profile_hooks.pos_profile_hooks import get_walk_in_customer

CACHE_PREFIX = "mypos_cdisplay:"
STATE_TTL_SECONDS = 12 * 3600
REALTIME_EVENT = "mypos_customer_display"
PHASES = ("idle", "cart", "order", "qr", "paid")
# Phase thu ngân được đặt trực tiếp qua API (các phase khác do server tự đặt).
SETTABLE_PHASES = ("idle", "order")
ORDER_PHASES = ("order", "qr", "paid")


# ---------------------------------------------------------------------------
# Lưu trạng thái
# ---------------------------------------------------------------------------


def _key(user):
	return f"{CACHE_PREFIX}{user}"


def _read(user):
	state = frappe.cache.get_value(_key(user))
	return state if isinstance(state, dict) else {"v": 0, "phase": "idle"}


def _write(user, state):
	"""Ghi trạng thái + báo realtime. v = mốc thời gian ms (không trùng sau khi cache hết hạn)."""
	state = dict(state)
	state["v"] = int(time.time() * 1000)
	frappe.cache.set_value(_key(user), state, expires_in_sec=STATE_TTL_SECONDS)
	try:
		frappe.publish_realtime(REALTIME_EVENT, {"v": state["v"]}, user=user)
	except Exception:
		# Socket không chạy -> màn khách vẫn nhận qua poll.
		pass
	return state


def _after_commit(fn):
	"""Chạy fn sau khi giao dịch DB commit (cache không theo giao dịch: tránh báo Paid khi submit bị rollback)."""
	hooks = getattr(frappe.db, "after_commit", None)
	if hooks is not None and hasattr(hooks, "add"):
		hooks.add(fn)
	else:
		fn()


def _safe(fn):
	"""Bọc điểm móc từ luồng bán hàng: lỗi chỉ ghi Error Log."""

	def wrapper(*args, **kwargs):
		try:
			return fn(*args, **kwargs)
		except Exception:
			frappe.log_error(title="MYPOS màn khách: lỗi cập nhật trạng thái", message=frappe.get_traceback())

	wrapper.__name__ = fn.__name__
	wrapper.__doc__ = fn.__doc__
	return wrapper


def _require_display_user():
	from .pos_api import _require_sale_role

	_require_sale_role()
	return frappe.session.user, resolve_pos_profile_name()


# ---------------------------------------------------------------------------
# Dựng dữ liệu hiển thị (dùng chung cho giỏ trong bộ nhớ và POS Invoice đã lưu)
# ---------------------------------------------------------------------------


def _lines(invoice):
	"""Dòng món: tên, size, tùy chọn (kèm giá phụ thu), qty, giá sau CTKM, thành tiền gồm phụ thu."""
	from ..doctype.mypos_option_group.option_resolver import read_line_options
	from .pos_api import _size_labels

	sizes = _size_labels([row.item_code for row in invoice.items])
	out = []
	for row in invoice.items:
		free = cint(row.get("is_free_item"))
		qty = flt(row.qty)
		options = read_line_options(row.get("options"), row.get("sugar_level"), row.get("ice_level"))
		unit_surcharge = 0 if free else sum(flt(o.get("price")) for o in options)
		rate = 0 if free else flt(row.rate)
		out.append(
			{
				"item_name": row.item_name or row.item_code,
				"size": sizes.get(row.item_code, ""),
				"qty": qty,
				"options": options,
				"price_list_rate": flt(row.price_list_rate),
				"rate": rate,
				"amount": rate * qty + unit_surcharge * qty,
				"is_free_item": free,
			}
		)
	return out


def _totals(invoice, paid=False):
	from .pos_api import _invoice_surcharge

	total_before = sum(
		flt(row.price_list_rate) * flt(row.qty) for row in invoice.items if not cint(row.get("is_free_item"))
	)
	due = flt(invoice.rounded_total or invoice.grand_total)
	return {
		"total_before": total_before,
		"total_discount_rules": total_before - flt(invoice.total),
		"total_surcharge": flt(_invoice_surcharge(invoice)),
		"loyalty_discount": flt(invoice.discount_amount),
		"redeemed_points": int(flt(invoice.get("redeemed_points"))),
		"grand_total": flt(invoice.grand_total),
		"amount_due": 0 if paid else due,
		"amount_total": due,
	}


def _customer(profile_name, company, customer, customer_name=None):
	from .pos_api import _loyalty_info

	walk_in = get_walk_in_customer(profile_name)
	is_walk_in = bool(walk_in) and customer == walk_in
	info = None if is_walk_in else _loyalty_info(customer, company, 0, walk_in)
	return {
		"name": "" if is_walk_in else (customer_name or frappe.db.get_value("Customer", customer, "customer_name") or ""),
		"is_walk_in": is_walk_in,
		"tier_name": (info or {}).get("tier_name") or "",
		"loyalty_points": (info or {}).get("loyalty_points") if info else None,
	}


def _invoice_view(invoice_name):
	"""Dữ liệu một đơn đã lưu (đọc lại lúc màn khách hỏi). None nếu đơn không còn hiển thị được."""
	if not invoice_name or not frappe.db.exists("POS Invoice", invoice_name):
		return None
	invoice = frappe.get_doc("POS Invoice", invoice_name)
	if invoice.docstatus == 2:
		return None
	paid = invoice.docstatus == 1 and invoice.status in ("Paid", "Consolidated")
	return {
		"invoice": invoice.name,
		"order_type": invoice.order_type,
		"currency": invoice.currency,
		"lines": _lines(invoice),
		"totals": _totals(invoice, paid=paid),
		"customer": _customer(invoice.pos_profile, invoice.company, invoice.customer, invoice.customer_name),
		"paid": paid,
	}


# ---------------------------------------------------------------------------
# Điểm móc từ luồng bán hàng (pos_api, pos_invoice_hooks, order_cancel)
# ---------------------------------------------------------------------------


@_safe
def touch_cart(profile, invoice, customer, loyalty=None):
	"""preview_pricing(display=1): lưu giỏ đã tính (hóa đơn tạm trong bộ nhớ, chưa insert)."""
	walk_in = get_walk_in_customer(profile)
	is_walk_in = bool(walk_in) and customer == walk_in
	cart = {
		"currency": invoice.currency,
		"lines": _lines(invoice),
		"totals": _totals(invoice),
		"customer": {
			"name": "" if is_walk_in else (frappe.db.get_value("Customer", customer, "customer_name") or ""),
			"is_walk_in": is_walk_in,
			"tier_name": (loyalty or {}).get("tier_name") or "",
			"loyalty_points": (loyalty or {}).get("loyalty_points") if loyalty else None,
		},
	}
	_write(frappe.session.user, {"phase": "cart", "pos_profile": profile.name, "cart": cart})


@_safe
def touch_order(invoice_name, pos_profile, qr=None):
	"""Đơn vừa tạo (create_draft_order) hoặc vừa sinh QR (generate_qr) -> màn khách hiện đơn đó."""
	user = frappe.session.user
	state = {"phase": "qr" if qr else "order", "pos_profile": pos_profile, "invoice": invoice_name}
	if qr:
		state["qr"] = {
			"qr_url": qr.get("qr_url") or "",
			"amount": flt(qr.get("amount")),
			"payment_code": qr.get("payment_code") or "",
		}
	_after_commit(lambda: _write(user, state))


def _users_showing(invoice_name, owner):
	"""User có màn khách đang hiện đơn này (người tạo đơn + người đang thao tác)."""
	users = []
	for user in (owner, frappe.session.user):
		if user and user not in users and user != "Guest" and _read(user).get("invoice") == invoice_name:
			users.append(user)
	return users


@_safe
def touch_paid(doc):
	"""Hook on_submit (status Paid): màn khách đang hiện đơn này -> "Thanh toán thành công", phải thu 0."""
	if doc.status != "Paid":
		return
	for user in _users_showing(doc.name, doc.owner):
		state = _read(user)
		if state.get("phase") not in ORDER_PHASES:
			continue
		new_state = {
			"phase": "paid",
			"pos_profile": state.get("pos_profile") or doc.pos_profile,
			"invoice": doc.name,
			"paid_at": now_datetime().isoformat(),
		}
		_after_commit(lambda u=user, s=new_state: _write(u, s))


@_safe
def touch_cancelled(invoice_name, owner=None):
	"""order_cancel.cancel_draft: màn khách đang hiện đơn bị hủy -> về idle."""
	if owner is None:
		owner = frappe.db.get_value("POS Invoice", invoice_name, "owner")
	for user in _users_showing(invoice_name, owner):
		state = _read(user)
		_after_commit(lambda u=user, p=state.get("pos_profile"): _write(u, {"phase": "idle", "pos_profile": p}))


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_customer_display_config():
	"""Thương hiệu (Branch) + banner của POS Profile người gọi. Không trả cấu hình SePay / kế toán."""
	_user, profile_name = _require_display_user()
	from ..doctype.mypos_banner.mypos_banner import active_banners

	profile = frappe.db.get_value("POS Profile", profile_name, ["branch", "currency", "company"], as_dict=True)
	banners = active_banners(profile_name)
	return {
		"brand": get_brand_info(profile.branch) if profile.branch else {},
		"currency": profile.currency or frappe.db.get_value("Company", profile.company, "default_currency"),
		"pos_profile": profile_name,
		"banners": banners,
	}


@frappe.whitelist()
def get_customer_display_state(since=0):
	"""Trạng thái màn khách của chính user. Không đổi so với `since` -> {v, unchanged: true} (chỉ đọc cache)."""
	user, profile_name = _require_display_user()
	state = _read(user)
	v = int(state.get("v") or 0)
	if since and int(flt(since)) == v:
		return {"v": v, "unchanged": True}

	phase = state.get("phase") if state.get("phase") in PHASES else "idle"
	# Đổi POS Profile (gán user sang chi nhánh khác) -> không hiện dữ liệu cũ.
	if state.get("pos_profile") and state.get("pos_profile") != profile_name:
		phase = "idle"

	out = {"v": v, "phase": phase}
	if phase == "cart":
		out["order"] = state.get("cart")
	elif phase in ORDER_PHASES:
		view = _invoice_view(state.get("invoice"))
		if not view:
			out["phase"] = "idle"
		else:
			out["order"] = view
			if phase == "paid" or view["paid"]:
				out["phase"] = "paid"
				out["paid_at"] = state.get("paid_at") or ""
			elif phase == "qr" and state.get("qr"):
				out["qr"] = state["qr"]
	return out


@frappe.whitelist()
def set_customer_display(phase, invoice=None):
	"""Thu ngân đặt màn khách: "idle" (giỏ rỗng — chỉ khi đang hiện giỏ) hoặc "order" (chọn đơn Draft ở Orders)."""
	user, profile_name = _require_display_user()
	if phase not in SETTABLE_PHASES:
		frappe.throw(_("Trạng thái màn khách không hợp lệ."))
	state = _read(user)

	if phase == "idle":
		# Giỏ về rỗng sau khi tạo đơn không được xóa đơn đang hiện cho khách.
		if state.get("phase") in ("cart", "idle"):
			state = _write(user, {"phase": "idle", "pos_profile": profile_name})
		return {"v": state.get("v"), "phase": state.get("phase") or "idle"}

	row = frappe.db.get_value(
		"POS Invoice", invoice, ["name", "pos_profile", "docstatus", "is_return", "payment_code"], as_dict=True
	) if invoice else None
	if not row or row.pos_profile != profile_name or cint(row.docstatus) != 0 or cint(row.is_return):
		frappe.throw(_("Không hiển thị được đơn này trên màn khách."))
	if state.get("invoice") == row.name and state.get("phase") in ("order", "qr"):
		return {"v": state.get("v"), "phase": state.get("phase")}
	state = _write(user, {"phase": "order", "pos_profile": profile_name, "invoice": row.name})
	return {"v": state["v"], "phase": "order"}
