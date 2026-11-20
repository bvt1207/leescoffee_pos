"""Script Report "MYPOS Review Queue" (Đơn cần xử lý) — chỉ xem / tìm cho quản lý.

Dữ liệu: kitchen_status.review_orders (nơi duy nhất của truy vấn "cần xử lý"). Giải quyết đơn: nút "Xử lý đơn"
trên form POS Invoice (public/js/pos_invoice.js) gọi pos_api.resolve_open_order — report không có logic xử lý riêng.
Quyền: roles POS MANAGER + System Manager (JSON) và kiểm tra lại manager ở đây.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt


def execute(filters=None):
	from leescoffee_pos.leescoffee_pos.api.pos_api import _pos_roles
	from leescoffee_pos.leescoffee_pos.doctype.pos_invoice_hooks.kitchen_status import (
		REVIEW_OVERDUE_HOURS,
		review_orders,
	)

	if not _pos_roles()["manager"]:
		frappe.throw(_("Chỉ quản lý (POS MANAGER) được xem đơn cần xử lý."), frappe.PermissionError)

	filters = frappe._dict(filters or {})
	rows = review_orders(
		pos_profile=filters.get("pos_profile") or None,
		search=filters.get("search"),
		overdue_only=cint(filters.get("overdue_only")),
		limit=500,
		fields=["customer_name", "grand_total", "rounded_total", "currency", "order_type", "order_channel"],
	)

	columns = [
		{"fieldname": "name", "label": _("Đơn"), "fieldtype": "Link", "options": "POS Invoice", "width": 190},
		{"fieldname": "customer_name", "label": _("Khách"), "fieldtype": "Data", "width": 160},
		{"fieldname": "creation", "label": _("Tạo lúc"), "fieldtype": "Datetime", "width": 160},
		{"fieldname": "age_hours", "label": _("Chờ (giờ)"), "fieldtype": "Float", "precision": 1, "width": 90},
		{"fieldname": "overdue", "label": _("Quá {0} giờ").format(REVIEW_OVERDUE_HOURS), "fieldtype": "Check", "width": 90},
		{"fieldname": "custom_kitchen_status", "label": _("Trạng thái"), "fieldtype": "Data", "width": 170},
		{"fieldname": "kitchen_outcome_reason", "label": _("Lý do"), "fieldtype": "Data", "width": 260},
		{"fieldname": "amount", "label": _("Tổng tiền"), "fieldtype": "Currency", "options": "currency", "width": 120},
		{"fieldname": "consolidated", "label": _("Đã gộp khi đóng ca"), "fieldtype": "Check", "width": 110},
		{"fieldname": "pos_profile", "label": _("POS Profile"), "fieldtype": "Link", "options": "POS Profile", "width": 140},
		{"fieldname": "currency", "label": _("Tiền tệ"), "fieldtype": "Link", "options": "Currency", "hidden": 1},
	]
	data = [
		{
			"name": r.name,
			"customer_name": r.customer_name,
			"creation": r.creation,
			"age_hours": round(r.age_minutes / 60, 1),
			"overdue": 1 if r.age_minutes >= REVIEW_OVERDUE_HOURS * 60 else 0,
			"custom_kitchen_status": r.custom_kitchen_status,
			"kitchen_outcome_reason": r.kitchen_outcome_reason,
			"amount": flt(r.rounded_total or r.grand_total),
			"consolidated": 1 if r.consolidated_invoice else 0,
			"pos_profile": r.pos_profile,
			"currency": r.currency,
		}
		for r in rows
	]
	return columns, data
