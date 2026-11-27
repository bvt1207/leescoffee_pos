"""Role POS + quyền DocType (Custom DocPerm, permlevel 0) của app MYPOS.

`PERMS` / `ROLES` dưới đây là NGUỒN CHUẨN quyền cho 3 role MYPOS (POS CASHIER / POS KITCHEN / POS MANAGER).
Không dùng fixture Custom DocPerm (xem docs/rules/roles.md §3).

Gọi từ `mypos/setup/install.py`:
- after_install  -> site cài mới (lỗi được ném ra: cài thiếu quyền thì phải biết ngay).
- after_migrate  -> mỗi lần `bench migrate` (lỗi chỉ ghi Error Log + in cảnh báo, KHÔNG làm migrate thất bại).

Idempotent, CHỈ THÊM, không bao giờ xóa / tắt:
- Role chưa có -> tạo với desk_access theo ROLES. Role đã có -> không đổi.
- DocType trong PERMS chưa có Custom DocPerm nào -> setup_custom_perms MỘT lần (chép DocPerm chuẩn, role ERPNext
  khác không mất quyền).
- Chưa có dòng (parent, role, permlevel 0) -> add_permission. Khóa này trùng khóa của update_permission_property
  (Frappe v16 không lọc if_owner ở hàm đó).
- Cờ quyền trong PERMS đang 0 -> bật 1. Cờ khác (admin tự thêm) giữ nguyên.
- Dòng Custom DocPerm trùng (parent, role, permlevel) -> chỉ IN ra để xem tay, không xóa.
- Không đụng DocType ngoài PERMS, không đụng User Permission. Không có gì thiếu -> không ghi DB.
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
# MANAGER có thêm "report" trên POS Invoice (2026-11-21, ban đầu cho Script Report "MYPOS Review Queue" — đã bỏ 2026-11-23).
# Giữ cờ: hàm này không tắt cờ đã bật, và cờ vẫn cho MANAGER dùng Report view của POS Invoice. CASHIER không cần.
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
		"MYPOS Banner": ["read"],
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
		"MYPOS Banner": _MASTER_RW,
	},
}


def _ensure_roles(stats):
	for role, desk_access in ROLES.items():
		if frappe.db.exists("Role", role):
			continue  # role từ fixture / tạo tay: không đổi desk_access
		frappe.get_doc(
			{"doctype": "Role", "role_name": role, "desk_access": desk_access, "disabled": 0}
		).insert(ignore_permissions=True)
		stats["roles"] += 1


def _perm_row(doctype, role):
	"""Dòng Custom DocPerm theo (parent, role, permlevel 0) — CÙNG khóa mà
	frappe.permissions.update_permission_property dùng để tìm dòng cần bật cờ (không lọc if_owner)."""
	return frappe.db.get_value(
		"Custom DocPerm",
		{"parent": doctype, "role": role, "permlevel": 0},
		"name",
		order_by="creation asc, name asc",
	)


def _managed_doctypes():
	doctypes = []
	for doctypes_of_role in PERMS.values():
		for dt in doctypes_of_role:
			if dt not in doctypes:
				doctypes.append(dt)
	return doctypes


def _report_duplicates(doctypes, stats):
	"""Dòng Custom DocPerm trùng (parent, role, permlevel): chỉ in ra, KHÔNG xóa (có thể do admin thêm tay)."""
	for doctype in doctypes:
		groups = frappe.db.sql(
			"""SELECT role, permlevel, COUNT(*) AS n FROM `tabCustom DocPerm` WHERE parent = %s
			GROUP BY role, permlevel HAVING COUNT(*) > 1""",
			doctype,
			as_dict=True,
		)
		for g in groups:
			print(f"[mypos_roles] CẢNH BÁO: {g.n} dòng Custom DocPerm trùng ({doctype} / {g.role} / permlevel {g.permlevel}) — xem tay")
			stats["duplicates"] += 1


def _ensure_doctype(doctype, stats):
	"""Bảo đảm quyền của mọi role MYPOS trên MỘT DocType. Trả True nếu có ghi DB."""
	from frappe.permissions import add_permission, setup_custom_perms, update_permission_property

	changed = False
	if setup_custom_perms(doctype):
		stats["setup"] += 1
		changed = True

	for role, doctypes_of_role in PERMS.items():
		ptypes = doctypes_of_role.get(doctype)
		if not ptypes:
			continue
		name = _perm_row(doctype, role)
		if not name:
			add_permission(doctype, role, 0, "read")
			name = _perm_row(doctype, role)
			stats["rows"] += 1
			changed = True
		current = frappe.db.get_value("Custom DocPerm", name, ptypes, as_dict=True) or {}
		for ptype in ptypes:
			if not current.get(ptype):
				update_permission_property(doctype, role, 0, ptype, 1)
				stats["flags"] += 1
				changed = True

	if changed:
		frappe.clear_cache(doctype=doctype)
	return changed


def _log(title, raise_errors):
	frappe.log_error(title=title)
	print(f"[mypos_roles] LỖI: {title} — xem Error Log")
	if raise_errors:
		raise


def setup_roles_and_permissions(raise_errors=False):
	"""Bảo đảm 3 role + quyền theo PERMS. Lỗi từng bước: ghi Error Log, đi tiếp (raise_errors=True thì ném lại)."""
	stats = {"roles": 0, "setup": 0, "rows": 0, "flags": 0, "skipped": 0, "duplicates": 0, "errors": 0}

	try:
		_ensure_roles(stats)
		if stats["roles"]:
			frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		stats["errors"] += 1
		_log("MYPOS: tạo Role POS thất bại", raise_errors)

	for doctype in _managed_doctypes():
		if not frappe.db.exists("DocType", doctype):
			print(f"[mypos_roles] Bỏ qua {doctype}: DocType không tồn tại")
			stats["skipped"] += 1
			continue
		try:
			if _ensure_doctype(doctype, stats):
				frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			stats["errors"] += 1
			_log(f"MYPOS: cấp quyền DocType {doctype} thất bại", raise_errors)

	try:
		_report_duplicates([dt for dt in _managed_doctypes() if frappe.db.exists("DocType", dt)], stats)
	except Exception:
		stats["errors"] += 1
		_log("MYPOS: kiểm dòng quyền trùng thất bại", raise_errors)

	print(
		"[mypos_roles] Role tạo mới: {roles}, DocType chép DocPerm chuẩn: {setup}, dòng Custom DocPerm thêm: {rows}, "
		"cờ quyền bật: {flags}, DocType bỏ qua: {skipped}, nhóm dòng trùng (chỉ báo): {duplicates}, lỗi: {errors}".format(**stats)
	)
	return stats
