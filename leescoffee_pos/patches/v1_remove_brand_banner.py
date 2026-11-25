"""Bỏ Custom Field Branch.brand_banner (2026-11-25): ảnh đầu trang /order lấy từ MYPOS Banner (public).

Idempotent. Trước khi xóa: in + ghi Error Log danh sách Branch đang có ảnh (để quản lý biết ảnh nào từng dùng).
Không xóa bản ghi File (ảnh vẫn ở File Manager). Fixture không còn mục này nên migrate không tạo lại field.
"""

import frappe

FIELD = "Branch-brand_banner"


def execute():
	if not frappe.db.exists("Custom Field", FIELD):
		print("[brand_banner] Custom Field đã xóa trước đó: bỏ qua")
		return

	rows = []
	if frappe.db.has_column("Branch", "brand_banner"):
		rows = frappe.get_all(
			"Branch", filters=[["brand_banner", "is", "set"]], fields=["name", "brand_banner"], order_by="name asc"
		)
	for r in rows:
		print(f"[brand_banner] {r.name} -> {r.brand_banner}")
	if rows:
		frappe.log_error(
			title="MYPOS: sao lưu brand_banner trước khi xóa",
			message="\n".join(f"{r.name} -> {r.brand_banner}" for r in rows),
		)
	else:
		print("[brand_banner] Không Branch nào có ảnh")

	frappe.delete_doc("Custom Field", FIELD, ignore_permissions=True, force=True)
	frappe.clear_cache(doctype="Branch")
	frappe.db.commit()
	print(
		"[brand_banner] Đã xóa Custom Field; cột DB còn: "
		+ ("có" if frappe.db.has_column("Branch", "brand_banner") else "không")
	)
