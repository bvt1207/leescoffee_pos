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
from frappe.utils import flt, getdate, now_datetime, nowdate

from ..doctype.branch_config.branch_config import (
    get_brand_info,
    get_default_branch,
)

ORDER_TYPES = ("Take Away", "Dine In")
ORDER_CHANNEL = "POS"
WALK_IN = "Walk-in Customer"
LEVELS = (50, 70, 100)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_pos_profile(branch_name=None):
	"""Trả về POS Profile của chi nhánh (fallback: POS Profile duy nhất đang bật)."""
	branch_name = branch_name or get_default_branch()

	profile_name = None
	if branch_name:
		profile_name = frappe.db.get_value(
			"POS Profile",
			{"branch": branch_name, "disabled": 0},
			"name",
		)

	if not profile_name:
		profiles = frappe.get_all(
			"POS Profile",
			filters={"disabled": 0},
			pluck="name",
			limit=1,
		)
		profile_name = profiles[0] if profiles else None

	if not profile_name:
		frappe.throw(
			_("Chưa cấu hình POS Profile. Vui lòng tạo POS Profile cho chi nhánh trước khi dùng POS.")
		)

	return frappe.get_doc("POS Profile", profile_name)


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

def _normalize_items(items):
	"""Chuẩn hóa danh sách món gửi từ giao diện."""
	normalized = []

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
		row["sugar_level"] = _level(item.get("sugar"))
		row["ice_level"] = _level(item.get("ice"))

		if item.get("warehouse"):
			row["warehouse"] = item.get("warehouse")

		normalized.append(row)

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
	except Exception:
		frappe.throw(
			_(
				"Không mở được phiên POS cho POS Profile {0}. "
				"Vui lòng mở phiên POS (POS Opening Entry) trong Desk."
			).format(profile.name)
		)

	return opening.name


def _assign_buzzer(profile):
	"""Gán 1 thẻ rung còn trống cho đơn Dine In."""
	from ..doctype.leescoffee_buzzer.leescoffee_buzzer import LeescoffeeBuzzer

	branch = getattr(profile, "branch", None)
	if not branch:
		frappe.throw(
			_(
				"POS Profile {0} chưa được gán chi nhánh nên chưa thể gán thẻ rung "
				"cho đơn Dine In."
			).format(profile.name)
		)

	buzzer_name = LeescoffeeBuzzer.get_available_buzzer(branch)
	if not buzzer_name:
		frappe.throw(_("Chưa có thẻ rung sẵn sàng trong chi nhánh {0}.").format(branch))

	# Thẻ đang "Sẵn sàng" nhưng đã bị gán cho đơn khác (đơn Draft chưa thanh toán)
	# → không gán lại, tránh 2 đơn dùng chung 1 thẻ.
	others = frappe.get_all(
		"POS Invoice",
		filters={
			"buzzer": buzzer_name,
			"order_type": "Dine In",
			"docstatus": ["in", [0, 1]],
		},
		fields=["name", "custom_kitchen_status"],
	)

	for other in others:
		if (other.get("custom_kitchen_status") or "") != "Đã hoàn thành":
			frappe.throw(
				_("Thẻ rung {0} đang được dùng cho đơn {1}.").format(
					buzzer_name, other.get("name")
				)
			)

	return buzzer_name


def _buzzer_number(buzzer_name):
	if not buzzer_name:
		return None

	return frappe.db.get_value("Leescoffee Buzzer", buzzer_name, "buzzer_number")


# ---------------------------------------------------------------------------
# API giao diện
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_pos_config(branch_name=None):
	"""Thông tin cấu hình cho giao diện: thương hiệu, POS Profile, phương thức thanh toán."""
	profile = _get_pos_profile(branch_name)

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
	}


@frappe.whitelist()
def get_menu_items(price_list=None):
	"""Danh sách menu (nhóm món) để hiển thị trên màn hình chọn món."""
	from ..doctype.leescoffee_menu.leescoffee_menu import LeescoffeeMenu

	return LeescoffeeMenu.get_menu_with_items(price_list=price_list)


@frappe.whitelist()
def get_buzzers(branch_name=None):
	"""Danh sách thẻ rung của chi nhánh."""
	branch_name = branch_name or get_default_branch()

	buzzers = frappe.get_all(
		"Leescoffee Buzzer",
		filters={"branch": branch_name} if branch_name else {},
		fields=["name", "buzzer_number", "status", "branch"],
		order_by="buzzer_number asc",
	)

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
):
	"""Tạo POS Invoice ở trạng thái Draft từ giỏ hàng.

	- Thanh toán tại quầy: đơn được tạo Draft, nhân viên thu tiền ở màn Orders.
	- Thanh toán QR: đơn được tạo Draft, sinh mã VietQR, webhook SePay sẽ submit.
	"""
	from ..doctype.leescoffee_menu.leescoffee_menu import LeescoffeeMenu

	rows = _normalize_items(items)
	if not rows:
		frappe.throw(_("Chưa chọn món nào để tạo đơn."))

	if order_type not in ORDER_TYPES:
		frappe.throw(_("Loại đơn không hợp lệ."))

	profile = _get_pos_profile(branch_name)
	mode = _resolve_mode_of_payment(profile.company, mode_of_payment)

	# Price List bắt buộc — lấy từ menu đang chọn (cùng nguồn với get_menu_items).
	# Không fallback sang profile.selling_price_list.
	if not price_list:
		frappe.throw(_("Thiếu Price List của menu."))
	effective_price_list = price_list.strip()

	customer = _resolve_customer(customer_name)

	_ensure_opening_entry(profile)

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
		rate = LeescoffeeMenu.get_price_for_item(code, effective_price_list)
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
		row["rate"] = rate
		row["price_list_rate"] = rate
		invoice.append("items", row)

	if order_type == "Dine In":
		invoice.buzzer = _assign_buzzer(profile)

	# Đính giá theo đúng Price List của menu (POS Profile), không để ERPNext
	# tự điền giá từ Price List khác.
	invoice.selling_price_list = effective_price_list
	invoice.ignore_pricing_rule = 1

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
def get_orders(status="all", limit=50):
	"""Danh sách đơn cho màn hình Orders.

	status: "all" | "draft" | "paid"
	"""
	filters = {}
	if status == "draft":
		filters = {"docstatus": 0}
	elif status == "paid":
		filters = {"docstatus": 1, "status": "Paid"}

	orders = frappe.get_all(
		"POS Invoice",
		filters=filters,
		fields=[
			"name",
			"customer",
			"customer_name",
			"order_type",
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
		],
		order_by="creation desc",
		limit=limit,
	)

	for order in orders:
		order["amount"] = flt(order.get("rounded_total") or order.get("grand_total"))
		order["buzzer_number"] = _buzzer_number(order.get("buzzer"))

	return orders


@frappe.whitelist()
def get_order_detail(invoice_name):
	"""Chi tiết một đơn (món, tổng tiền, thanh toán, trạng thái bếp, thẻ rung)."""
	invoice = frappe.get_doc("POS Invoice", invoice_name)

	items = [
		{
			"item_code": row.item_code,
			"item_name": row.item_name,
			"qty": flt(row.qty),
			"rate": flt(row.rate),
			"amount": flt(row.amount),
			"sugar_level": row.get("sugar_level") or "",
			"ice_level": row.get("ice_level") or "",
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
		"buzzer": invoice.buzzer,
		"buzzer_number": _buzzer_number(invoice.buzzer),
		"grand_total": flt(invoice.grand_total),
		"amount": flt(invoice.rounded_total or invoice.grand_total),
		"currency": invoice.currency,
		"items": items,
		"payments": payments,
		"creation": invoice.creation,
		"order_note": invoice.get("order_note") or "",
	}


@frappe.whitelist()
def pay_cash(invoice_name):
	"""Thu tiền tại quầy: đặt đúng số tiền của đơn rồi submit."""
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
def cancel_draft_order(invoice_name, force=0):
	"""Hủy (xóa hẳn) đơn Draft chưa thanh toán.

	- Chỉ cho docstatus = 0. Đơn đã thanh toán không hủy được tại POS.
	- Đơn đã sinh QR (đang chờ chuyển khoản) cần force=1 để tránh xóa nhầm
	  đơn khách đã chuyển tiền.
	- Thẻ rung tự được nhả vì _assign_buzzer chỉ xét các POS Invoice còn tồn tại.
	"""
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
	frappe.delete_doc("POS Invoice", invoice_name, ignore_permissions=True)

	return {
		"invoice_name": invoice_name,
		"buzzer_number": buzzer_number,
		"message": _("Đã hủy đơn {0}.").format(invoice_name),
	}

@frappe.whitelist()
def generate_qr(invoice_name):
	"""Sinh mã VietQR cho đơn (idempotent — gọi lại trả về mã cũ)."""
	from ..doctype.sepay.sepay import generate_qr_for_invoice

	return generate_qr_for_invoice(invoice_name)


@frappe.whitelist()
def confirm_pickup(invoice_name):
	"""Nhân viên xác nhận khách đã lấy món → trả thẻ rung về kho."""
	from ..doctype.pos_invoice_hooks.pos_invoice_hooks import PosInvoiceHooks

	invoice = frappe.get_doc("POS Invoice", invoice_name)

	PosInvoiceHooks.confirm_pickup(invoice, method="confirm_pickup")

	return {
		"invoice_name": invoice.name,
		"buzzer_number": _buzzer_number(invoice.buzzer),
		"message": _("Đã xác nhận khách lấy món."),
	}


@frappe.whitelist()
def get_status_board():
	"""Bảng trạng thái bếp (đơn đã thanh toán, đang làm / hoàn thành)."""
	from ..doctype.pos_invoice_hooks.pos_invoice_hooks import get_status_board_orders

	return get_status_board_orders()
