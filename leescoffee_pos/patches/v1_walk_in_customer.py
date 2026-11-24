"""Khách vãng lai theo POS Profile (2026-11-24): điền `custom_walk_in_customer` cho profile đang trống.

- Ứng viên DUY NHẤT: Customer tên LEGACY_WALK_IN (tên mặc định cũ của app). Đây là nơi duy nhất trong code còn
  chuỗi này — hằng di trú một lần; code chạy (pos_api, ...) chỉ đọc field của POS Profile.
- Chỉ gán khi Customer tồn tại, không disabled, KHÔNG gắn Loyalty Program (khớp pos_profile_hooks.validate).
- Không gán được -> để trống, in + Error Log danh sách profile cần cấu hình tay. KHÔNG tạo Customer.
- Profile đã có giá trị: không đụng. Không sửa hóa đơn cũ. Idempotent.
- Fixture nạp SAU patch post_model_sync -> lần migrate đầu cột chưa có: patch tự tạo Custom Field với định nghĩa
  GIỐNG HỆT fixtures/custom_field.json (cùng tên "POS Profile-custom_walk_in_customer"; fixture nạp sau ghi đè y nguyên).
"""

import frappe

LEGACY_WALK_IN = "Walk-in Customer"
FIELD = "custom_walk_in_customer"
FIELD_DEF = {
	"fieldname": FIELD,
	"label": "Khách vãng lai",
	"fieldtype": "Link",
	"options": "Customer",
	"insert_after": "branch",
	"description": "Customer dùng cho khách không cung cấp thông tin. Tạo sẵn trong Customer rồi chọn ở đây.",
}


def _ensure_field():
	if frappe.db.has_column("POS Profile", FIELD):
		return
	from frappe.custom.doctype.custom_field.custom_field import create_custom_field

	create_custom_field("POS Profile", FIELD_DEF)
	frappe.clear_cache(doctype="POS Profile")
	print(f"[walk_in_customer] Tạo Custom Field POS Profile-{FIELD} (fixture sẽ nạp lại cùng định nghĩa)")


def execute():
	_ensure_field()
	# Đọc thẳng schema (không qua cache cột) để chắc cột vừa tạo đã có.
	if not frappe.db.sql("SHOW COLUMNS FROM `tabPOS Profile` LIKE %s", FIELD):
		print(f"[walk_in_customer] Không tạo được cột {FIELD}: bỏ qua, cấu hình tay sau migrate")
		return

	empty = frappe.get_all(
		"POS Profile",
		filters=[[FIELD, "is", "not set"]],
		fields=["name", "disabled"],
		order_by="name asc",
	)
	if not empty:
		print("[walk_in_customer] Mọi POS Profile đã cấu hình Khách vãng lai: không làm gì")
		return

	cust = frappe.db.get_value("Customer", LEGACY_WALK_IN, ["name", "disabled", "loyalty_program"], as_dict=True)
	reason = None
	if not cust:
		reason = f"không có Customer '{LEGACY_WALK_IN}'"
	elif cust.disabled:
		reason = f"Customer '{LEGACY_WALK_IN}' đang disabled"
	elif cust.loyalty_program:
		reason = f"Customer '{LEGACY_WALK_IN}' gắn Loyalty Program {cust.loyalty_program}"

	if reason:
		names = [p.name for p in empty]
		msg = (
			f"{len(names)} POS Profile chưa có Khách vãng lai ({reason}). Tạo Customer khách vãng lai "
			f"(không SĐT, không Loyalty Program) rồi chọn ở POS Profile > Khách vãng lai: {names}"
		)
		print(f"[walk_in_customer] CẦN CẤU HÌNH TAY: {msg}")
		frappe.log_error(title="Leescoffee POS: POS Profile thiếu Khách vãng lai", message=msg)
		frappe.db.commit()
		return

	for p in empty:
		frappe.db.set_value("POS Profile", p.name, FIELD, cust.name, update_modified=False)
	frappe.db.commit()
	print(f"[walk_in_customer] Gán '{cust.name}' cho {len(empty)} POS Profile: {[p.name for p in empty]}")
