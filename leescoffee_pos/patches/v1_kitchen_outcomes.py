"""Trạng thái kết thúc đơn pha chế (2026-11-20): bổ sung options cho POS Invoice.custom_kitchen_status.

Thêm "Khách không nhận", "Không thực hiện được", "Đã đóng ca chưa xử lý" (giữ nguyên giá trị cũ, không đổi kiểu field).
Fixture custom_field.json cũng có options này + 6 field người/giờ/lý do/needs_review; patch chỉ bảo đảm options đủ
nếu fixture chưa nạp. Idempotent, không đụng dữ liệu đơn.
"""

import frappe

FIELD = "POS Invoice-custom_kitchen_status"


def execute():
	from leescoffee_pos.leescoffee_pos.doctype.pos_invoice_hooks.kitchen_status import KITCHEN_STATUS_OPTIONS

	if not frappe.db.exists("Custom Field", FIELD):
		print(f"[kitchen_outcomes] Không có Custom Field {FIELD}: bỏ qua")
		return
	doc = frappe.get_doc("Custom Field", FIELD)
	current = [x for x in (doc.options or "").split("\n") if x.strip()]
	missing = [x for x in KITCHEN_STATUS_OPTIONS if x not in current]
	if not missing:
		print("[kitchen_outcomes] Options đã đủ")
		return
	doc.options = "\n".join(current + missing)
	doc.save(ignore_permissions=True)
	frappe.clear_cache(doctype="POS Invoice")
	print(f"[kitchen_outcomes] Thêm options: {missing}")
