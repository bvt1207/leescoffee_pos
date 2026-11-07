"""Giai đoạn 2: xóa DocType "Leescoffee POS Settings" (Branch là nguồn cấu hình duy nhất).

Chạy ở [post_model_sync]. Idempotent: chạy lại khi đã xóa thì không làm gì.
"""

import frappe

DOCTYPE = "Leescoffee POS Settings"


def execute():
	# Link còn sót trên Workspace / Sidebar / Desktop Icon (bảng có thể không tồn tại ở bản khác).
	for child, field in (
		("Workspace Link", "link_to"),
		("Workspace Shortcut", "link_to"),
		("Workspace Sidebar Item", "link_to"),
		("Desktop Icon", "link_to"),
	):
		if frappe.db.table_exists(child) and frappe.db.has_column(child, field):
			frappe.db.delete(child, {field: DOCTYPE})

	# Bản ghi Single của DocType.
	frappe.db.delete("Singles", {"doctype": DOCTYPE})

	# Quyền / tùy biến gắn theo DocType.
	for dt, field in (
		("Custom DocPerm", "parent"),
		("Property Setter", "doc_type"),
		("Custom Field", "dt"),
	):
		frappe.db.delete(dt, {field: DOCTYPE})

	if frappe.db.exists("DocType", DOCTYPE):
		frappe.delete_doc("DocType", DOCTYPE, force=1, ignore_missing=True, ignore_permissions=True)

	frappe.clear_cache()
