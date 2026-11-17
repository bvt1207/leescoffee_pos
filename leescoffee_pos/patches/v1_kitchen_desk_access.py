"""Bật desk_access = 1 cho role POS KITCHEN trên site đã có role (2026-11-17).

Quyết định: KITCHEN được vào /desk (thấy icon leescoffee_pos, bấm POS -> /pos tự chuyển /pos/kitchen).
Quyền DocType KHÔNG đổi (vẫn chỉ Read MYPOS Menu / Buzzer / Option Group — xem v1_create_pos_roles.PERMS).

Idempotent, chỉ đụng đúng phạm vi:
1. Role POS KITCHEN tồn tại và desk_access = 0 -> đặt 1 (db.set_value, không chạy hook Role để
   không lưu lại user khác). Role khác (CASHIER, MANAGER, ...) không đụng.
2. User đang bật, có role POS KITCHEN, user_type = "Website User" -> lưu lại User để Frappe tự tính lại
   user_type (System User vì đã có role có desk_access). User khác không đụng. In danh sách user đã đổi.
"""

import frappe

KITCHEN = "POS KITCHEN"


def execute():
	if not frappe.db.exists("Role", KITCHEN):
		print(f"[kitchen_desk] Không có role {KITCHEN}: bỏ qua")
		return

	role_changed = False
	if not int(frappe.db.get_value("Role", KITCHEN, "desk_access") or 0):
		frappe.db.set_value("Role", KITCHEN, "desk_access", 1)
		frappe.clear_document_cache("Role", KITCHEN)
		frappe.clear_cache()
		role_changed = True

	users = frappe.get_all(
		"Has Role",
		filters={"role": KITCHEN, "parenttype": "User"},
		pluck="parent",
		distinct=True,
	)
	changed, still = [], []
	for name in users:
		row = frappe.db.get_value("User", name, ["enabled", "user_type"], as_dict=True)
		if not row or not row.enabled or row.user_type != "Website User":
			continue
		user = frappe.get_doc("User", name)
		user.flags.ignore_permissions = True
		user.save(ignore_permissions=True)  # User.validate -> set_system_user tính lại user_type
		if frappe.db.get_value("User", name, "user_type") == "System User":
			changed.append(name)
		else:
			still.append(name)

	frappe.db.commit()
	print(
		f"[kitchen_desk] desk_access {KITCHEN}: {'0 -> 1' if role_changed else 'đã là 1, không đổi'}; "
		f"user đổi Website User -> System User: {changed or 'không có'}"
	)
	if still:
		print(f"[kitchen_desk] CẢNH BÁO: vẫn là Website User sau khi lưu (kiểm tra User Type tùy biến): {still}")
