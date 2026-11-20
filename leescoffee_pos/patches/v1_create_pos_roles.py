"""Tạo sẵn 3 Role POS + quyền DocType (Custom DocPerm, permlevel 0).

Gọi từ:
- patches.txt [post_model_sync]  -> site đang chạy (bench migrate, chạy 1 lần).
- hooks.after_install            -> site cài mới (install-app không chạy patch).

Idempotent, chỉ BẬT quyền, không bao giờ tắt:
- Role chưa có -> tạo với desk_access theo ROLES. Role đã có -> KHÔNG đổi desk_access
  (site cũ có POS KITCHEN desk_access = 0: patch riêng v1_kitchen_desk_access bật lên 1).
- DocType chưa có Custom DocPerm nào -> setup_custom_perms MỘT lần (chép DocPerm chuẩn, role ERPNext
  khác không mất quyền). setup_custom_perms tự bỏ qua nếu đã có.
- Dọn trùng (parent, role, permlevel): giữ dòng cũ nhất, xóa dòng sau CHỈ khi mọi cột quyền giống hệt.
- Chưa có dòng (parent, role, permlevel 0) -> add_permission. Khóa này trùng khóa của
  update_permission_property (Frappe v16 không lọc if_owner ở hàm đó).
- Cờ quyền trong bảng đang 0 -> bật 1. Cờ khác (do người dùng tự thêm) giữ nguyên.
Không cấp cancel/delete/amend.
"""

import frappe

CASHIER = "POS CASHIER"
KITCHEN = "POS KITCHEN"
MANAGER = "POS MANAGER"

# role -> desk_access (chỉ dùng khi TẠO MỚI role). KITCHEN = 1 từ 2026-11-17: vào /desk, bấm POS
# -> /pos/kitchen; quyền DocType vẫn tối thiểu (chỉ Read, xem PERMS).
ROLES = {
	CASHIER: 1,
	KITCHEN: 1,
	MANAGER: 1,
}

_SHIFT = ["select", "read", "write", "create", "submit"]
# CASHIER chỉ thấy / sửa ca và phiếu đóng ca do chính mình tạo (Only If Creator, 2026-11-20).
# Ca MANAGER mở thay thì Cashier không thấy trên Desk -> MANAGER đóng thay. Quy tắc mở/đóng: pos_shift_hooks.py.
_SHIFT_CASHIER = _SHIFT + ["if_owner"]
_INVOICE = ["select", "read", "write", "create", "submit"]
# MANAGER cần thêm "report" trên POS Invoice: Script Report "MYPOS Review Queue" (ref_doctype POS Invoice) bị Frappe chặn nếu
# thiếu (frappe.desk.query_report.get_report_doc kiểm has_permission(ref_doctype, "report")). CASHIER không cần (2026-11-21).
_INVOICE_MANAGER = _INVOICE + ["report"]
_MASTER_RW = ["select", "read", "write", "create"]

# role -> {doctype: [ptype, ...]}
PERMS = {
	CASHIER: {
		"POS Opening Entry": _SHIFT_CASHIER,
		"POS Closing Entry": _SHIFT_CASHIER,
		"POS Profile": ["select", "read"],
		"MYPOS Menu": ["read"],
		"MYPOS Buzzer": ["read"],
		"Account": ["read"],
		"Customer": ["read"],
		"Item": ["read"],
		"POS Invoice": _INVOICE,
		"POS Invoice Merge Log": _INVOICE,
		"Sales Invoice": _INVOICE,
		"Address": ["read"],
		"Contact": ["read"],
		"MYPOS Option Group": ["read"],
		"MYPOS Order QR": ["read"],
	},
	KITCHEN: {
		"MYPOS Menu": ["read"],
		"MYPOS Buzzer": ["read"],
		"MYPOS Option Group": ["read"],
	},
	MANAGER: {
		"POS Opening Entry": _SHIFT,
		"POS Closing Entry": _SHIFT,
		"POS Profile": _MASTER_RW,
		"MYPOS Menu": _MASTER_RW,
		"MYPOS Buzzer": _MASTER_RW,
		"Account": _MASTER_RW,
		"Customer": _MASTER_RW,
		"Item": _MASTER_RW,
		"POS Invoice": _INVOICE_MANAGER,
		"POS Invoice Merge Log": _INVOICE,
		"Sales Invoice": _INVOICE,
		"Address": ["read", "write", "create"],
		"Contact": ["read", "write", "create"],
		"Branch": _MASTER_RW,
		"MYPOS Option Group": ["read", "write", "create"],
		"MYPOS Order QR": _MASTER_RW,
		# Nhật ký hủy đơn (2026-11-20): xem + bỏ cờ "Cần đối soát". Không tạo/xóa (log do hệ thống ghi).
		"MYPOS Order Cancel Log": ["select", "read", "write"],
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
	"""Dòng Custom DocPerm theo (parent, role, permlevel 0) — CÙNG khóa mà
	frappe.permissions.update_permission_property dùng để tìm dòng cần bật cờ (không lọc if_owner).
	Trước đây lọc thêm if_owner = 0 nên hai hàm có thể nhìn hai dòng khác nhau."""
	return frappe.db.get_value(
		"Custom DocPerm",
		{"parent": doctype, "role": role, "permlevel": 0},
		"name",
		order_by="creation asc, name asc",
	)


def _perm_columns():
	"""Mọi cột quyền (Check) của Custom DocPerm, kể cả if_owner — dùng để so 'quyền giống hệt'."""
	return [df.fieldname for df in frappe.get_meta("Custom DocPerm").fields if df.fieldtype == "Check"]


def _dedupe_perms(doctypes, stats):
	"""Dọn dòng Custom DocPerm trùng (parent, role, permlevel), idempotent.

	Giữ dòng cũ nhất (creation, rồi name); chỉ xóa dòng sau khi MỌI cột quyền giống hệt dòng giữ lại.
	Dòng trùng nhưng khác quyền -> giữ nguyên, chỉ in ra để xem tay.
	Áp dụng cho mọi role trên các DocType patch này quản lý (gồm role chuẩn ERPNext).
	"""
	cols = _perm_columns()
	for doctype in doctypes:
		groups = frappe.db.sql(
			"""SELECT role, permlevel FROM `tabCustom DocPerm` WHERE parent = %s
			GROUP BY role, permlevel HAVING COUNT(*) > 1""",
			doctype,
			as_dict=True,
		)
		for g in groups:
			# SQL thô + backtick: các cột `select`, `import`, `print`... là từ khóa SQL.
			col_sql = ", ".join(f"`{c}`" for c in cols)
			rows = frappe.db.sql(
				f"""SELECT name, {col_sql} FROM `tabCustom DocPerm`
				WHERE parent = %s AND role = %s AND permlevel = %s ORDER BY creation ASC, name ASC""",
				(doctype, g.role, g.permlevel),
				as_dict=True,
			)
			keep = rows[0]
			for r in rows[1:]:
				if all((r.get(c) or 0) == (keep.get(c) or 0) for c in cols):
					frappe.delete_doc("Custom DocPerm", r.name, ignore_permissions=True, force=True)
					print(f"[pos_roles] Xóa Custom DocPerm trùng {r.name} ({doctype} / {g.role}), giữ {keep.name}")
					stats["dups_removed"] += 1
				else:
					print(f"[pos_roles] Trùng nhưng KHÁC quyền, giữ nguyên: {r.name} vs {keep.name} ({doctype} / {g.role})")
					stats["dups_kept"] += 1
		if groups:
			frappe.clear_cache(doctype=doctype)


def _ensure_perms(stats):
	from frappe.permissions import add_permission, setup_custom_perms, update_permission_property

	doctypes = []
	for doctypes_of_role in PERMS.values():
		for dt in doctypes_of_role:
			if dt not in doctypes:
				doctypes.append(dt)

	existing = [dt for dt in doctypes if frappe.db.exists("DocType", dt)]
	for dt in doctypes:
		if dt not in existing:
			print(f"[pos_roles] Bỏ qua {dt}: DocType không tồn tại")
			stats["skipped"] += 1

	# 1) Mỗi DocType chưa có Custom DocPerm -> chép DocPerm chuẩn MỘT lần (setup_custom_perms tự kiểm tra).
	for dt in existing:
		if setup_custom_perms(dt):
			stats["setup"] += 1

	# 2) Dọn trùng có sẵn (vd. từ 08/11) trước khi kiểm tra/thêm dòng.
	_dedupe_perms(existing, stats)

	# 3) Thêm dòng còn thiếu: chỉ add_permission khi CHƯA có (parent, role, permlevel 0).
	for role, doctypes_of_role in PERMS.items():
		for doctype, ptypes in doctypes_of_role.items():
			if doctype not in existing:
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
	stats = {"roles": 0, "setup": 0, "dups_removed": 0, "dups_kept": 0, "rows": 0, "flags": 0, "skipped": 0}
	_ensure_roles(stats)
	_ensure_perms(stats)
	frappe.db.commit()
	print(
		"[pos_roles] Role tạo mới: {roles}, DocType chép DocPerm chuẩn: {setup}, dòng trùng đã xóa: {dups_removed}, "
		"trùng khác quyền giữ lại: {dups_kept}, dòng Custom DocPerm thêm: {rows}, "
		"cờ quyền bật: {flags}, DocType bỏ qua: {skipped}".format(**stats)
	)
	return stats
