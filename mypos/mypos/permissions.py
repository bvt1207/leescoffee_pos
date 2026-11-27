"""Quyền thấy app MYPOS trên màn Apps của Desk (hook `add_to_apps_screen` -> `has_permission`).

Frappe 16.61 gọi hàm này không tham số, cho user đang đăng nhập (`frappe.apps.get_apps`, `frappe.boot.get_app_data`).
"""

import frappe

# Role POS của app: nguồn chuẩn ở mypos/setup/roles.py (ROLES). Workspace "MYPOS Admin" dùng System Manager.
ADMIN_ROLES = ("System Manager",)


def has_app_permission() -> bool:
	"""True khi user có ít nhất một role POS của app (CASHIER / KITCHEN / MANAGER) hoặc System Manager / Administrator."""
	from mypos.setup.roles import ROLES

	user = frappe.session.user
	if not user or user == "Guest":
		return False
	if user == "Administrator":
		return True
	roles = set(frappe.get_roles(user))
	return bool(roles.intersection(ROLES) or roles.intersection(ADMIN_ROLES))
