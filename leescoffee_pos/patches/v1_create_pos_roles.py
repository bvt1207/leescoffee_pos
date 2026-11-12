"""Tạo sẵn 3 Role POS + quyền DocType (Custom DocPerm, permlevel 0).

Gọi từ:
- patches.txt [post_model_sync]  -> site đang chạy (bench migrate, chạy 1 lần).
- hooks.after_install            -> site cài mới (install-app không chạy patch).

Idempotent, chỉ BẬT quyền, không bao giờ tắt:
- Role chưa có -> tạo với desk_access theo ROLES. Role đã có -> KHÔNG đổi desk_access.
- Chưa có dòng Custom DocPerm (role, doctype, permlevel 0, if_owner 0) -> add_permission.
  add_permission tự gọi setup_custom_perms để chép DocPerm chuẩn trước (role ERPNext
  khác không mất quyền).
- Cờ quyền trong bảng đang 0 -> bật 1. Cờ khác (do người dùng tự thêm) giữ nguyên.
Không cấp cancel/delete/amend.
"""

import frappe

CASHIER = "POS CASHIER"
KITCHEN = "POS KITCHEN"
MANAGER = "POS MANAGER"

# role -> desk_access (chỉ dùng khi TẠO MỚI role)
ROLES = {
	CASHIER: 1,
	KITCHEN: 0,
	MANAGER: 1,
}

_SHIFT = ["select", "read", "write", "create", "submit"]
_INVOICE = ["select", "read", "write", "create", "submit"]
_MASTER_RW = ["select", "read", "write", "create"]

# role -> {doctype: [ptype, ...]}
PERMS = {
	CASHIER: {
		"POS Opening Entry": _SHIFT,
		"POS Closing Entry": _SHIFT,
		"POS Profile": ["select", "read"],
		"Leescoffee Menu": ["read"],
		"Leescoffee Buzzer": ["read"],
		"Account": ["read"],
		"Customer": ["read"],
		"Item": ["read"],
		"POS Invoice": _INVOICE,
		"POS Invoice Merge Log": _INVOICE,
		"Sales Invoice": _INVOICE,
		"Address": ["read"],
		"Contact": ["read"],
	},
	KITCHEN: {
		"Leescoffee Menu": ["read"],
		"Leescoffee Buzzer": ["read"],
	},
	MANAGER: {
		"POS Opening Entry": _SHIFT,
		"POS Closing Entry": _SHIFT,
		"POS Profile": _MASTER_RW,
		"Leescoffee Menu": _MASTER_RW,
		"Leescoffee Buzzer": _MASTER_RW,
		"Account": _MASTER_RW,
		"Customer": _MASTER_RW,
		"Item": _MASTER_RW,
		"POS Invoice": _INVOICE,
		"POS Invoice Merge Log": _INVOICE,
		"Sales Invoice": _INVOICE,
		"Address": ["read", "write", "create"],
		"Contact": ["read", "write", "create"],
		"Branch": _MASTER_RW,
	},
}


def _ensure_roles(stats):
	for role, desk_access in ROLES.items():
		if frappe.db.exists("Role", role):
			continue  # role tạo tay / từ fixture: không đổi desk_access
		frappe.get_doc(
			{"doctype": "Role", "role_name": role, "desk_access": desk_access, "disabled": 0}
		).insert(ignore_permissions=True)
		stats["roles"] += 1


def _perm_row(doctype, role):
	return frappe.db.get_value(
		"Custom DocPerm",
		{"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0},
		"name",
	)


def _ensure_perms(stats):
	from frappe.permissions import add_permission, update_permission_property

	for role, doctypes in PERMS.items():
		for doctype, ptypes in doctypes.items():
			if not frappe.db.exists("DocType", doctype):
				print(f"[pos_roles] Bỏ qua {doctype}: DocType không tồn tại")
				stats["skipped"] += 1
				continue

			name = _perm_row(doctype, role)
			if not name:
				add_permission(doctype, role, 0, "read")
				name = _perm_row(doctype, role)
				stats["rows"] += 1

			current = frappe.db.get_value("Custom DocPerm", name, ptypes, as_dict=True) or {}
			for ptype in ptypes:
				if not current.get(ptype):
					update_permission_property(doctype, role, 0, ptype, 1)
					stats["flags"] += 1

			frappe.clear_cache(doctype=doctype)


def execute():
	stats = {"roles": 0, "rows": 0, "flags": 0, "skipped": 0}
	_ensure_roles(stats)
	_ensure_perms(stats)
	frappe.db.commit()
	print(
		"[pos_roles] Role tạo mới: {roles}, dòng Custom DocPerm thêm: {rows}, "
		"cờ quyền bật: {flags}, DocType bỏ qua: {skipped}".format(**stats)
	)
	return stats
