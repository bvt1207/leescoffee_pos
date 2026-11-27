"""Workspace theo vai trò, tiền tố MYPOS (2026-11-25).

Chạy ở [post_model_sync]: lúc này `sync_all` đã import các file workspace / sidebar mới.
Idempotent, chạy lại không đổi gì nếu DB đã khớp file.

1. Mỗi workspace MYPOS: so số dòng Workspace Link / Workspace Shortcut / Has Role trong DB với file JSON, và (2026-11-27)
   danh sách shortcut (nhãn + URL) — đổi nhãn / thêm shortcut mà số dòng không đổi vẫn được phát hiện.
   Thiếu workspace hoặc lệch (gồm dòng trùng) -> import lại file với force=True (Frappe xóa doc cũ
   cùng mọi dòng con rồi insert lại, `import_file.import_doc`). KHÔNG xóa Workspace Link bằng SQL ở đây:
   patch chạy SAU khi file đã nạp, xóa sẽ mất dữ liệu vừa nạp.
2. Đủ 4 workspace mới -> xóa workspace cũ `leescoffee_pos` (đã thay bằng "MYPOS Admin"), Desktop Icon cũ
   `leescoffee_pos`, Workspace Sidebar cũ `leescoffee_pos` (chỉ khi Workspace Sidebar "MYPOS" đã nạp, tức Frappe < 16.50).
3. Frappe >= 16.50 (có DocType `Sidebar`): bảo đảm Sidebar "MYPOS" khớp file; xóa Sidebar KHÔNG chuẩn
   (standard = 0) khác của module (bản `convert_sidebars` tự chuyển từ Workspace Sidebar cũ) để module chỉ còn 1 sidebar.
Chỉ IN cảnh báo (không xóa) lớp tùy chỉnh trên Desk: Custom Workspace / Custom Sidebar.
"""

import json
import os

import frappe
from frappe.modules.import_file import import_file_by_path

MODULE = "Leescoffee POS"
WORKSPACES = {
	"MYPOS Cashier": "mypos_cashier",
	"MYPOS Kitchen": "mypos_kitchen",
	"MYPOS Manager": "mypos_manager",
	"MYPOS Admin": "mypos_admin",
}
OLD_NAME = "leescoffee_pos"  # tên cũ của workspace, Desktop Icon và Workspace Sidebar
NEW_SIDEBAR = "MYPOS"
CHILD_TABLES = {"links": "Workspace Link", "shortcuts": "Workspace Shortcut", "roles": "Has Role"}


def _module_path(*parts):
	return os.path.join(frappe.get_module_path(MODULE), *parts)


def _load(path):
	with open(path, encoding="utf-8") as f:
		return json.load(f)


def _expected(data):
	out = {dt: len(data.get(field) or []) for field, dt in CHILD_TABLES.items()}
	out["shortcuts"] = sorted((s.get("label") or "", s.get("url") or "") for s in data.get("shortcuts") or [])
	return out


def _actual(name):
	out = {dt: frappe.db.count(dt, {"parent": name, "parenttype": "Workspace"}) for dt in CHILD_TABLES.values()}
	out["shortcuts"] = sorted(
		(r.label or "", r.url or "")
		for r in frappe.get_all(
			"Workspace Shortcut", filters={"parent": name, "parenttype": "Workspace"}, fields=["label", "url"]
		)
	)
	return out


def _sync_workspaces():
	ok = True
	for name, folder in WORKSPACES.items():
		path = _module_path("workspace", folder, f"{folder}.json")
		if not os.path.exists(path):
			print(f"[mypos_ws] THIẾU file {path} -> bỏ qua (chưa copy?)")
			ok = False
			continue
		expected = _expected(_load(path))
		if frappe.db.exists("Workspace", name) and _actual(name) == expected:
			print(f"[mypos_ws] {name}: khớp file {expected}")
			continue
		before = _actual(name) if frappe.db.exists("Workspace", name) else None
		import_file_by_path(path, force=True)
		after = _actual(name)
		print(f"[mypos_ws] {name}: import lại (force). Trước {before} -> sau {after}, file {expected}")
		if after != expected:
			print(f"[mypos_ws] CẢNH BÁO {name}: vẫn lệch sau import lại, xem workspace.md §7 (xóa tay dự phòng)")
			ok = False
	return ok


def _warn_custom_layers():
	if frappe.db.exists("DocType", "Custom Workspace"):
		rows = frappe.get_all(
			"Custom Workspace", filters={"workspace": ["in", [*WORKSPACES, OLD_NAME]]}, pluck="workspace"
		)
		if rows:
			print(f"[mypos_ws] CẢNH BÁO: có Custom Workspace (tùy chỉnh trên Desk) cho {rows} — có thể ghi đè roles/nội dung file")
	if frappe.db.exists("DocType", "Custom Sidebar"):
		count = frappe.db.count("Custom Sidebar", {"module": MODULE})
		if count:
			print(f"[mypos_ws] CẢNH BÁO: có {count} Custom Sidebar của module {MODULE} (sắp xếp riêng của user/site)")


def _remove_old():
	if frappe.db.exists("Workspace", OLD_NAME):
		frappe.delete_doc("Workspace", OLD_NAME, force=True, ignore_missing=True)
		print(f"[mypos_ws] Đã xóa workspace cũ {OLD_NAME} (thay bằng MYPOS Admin)")
	if frappe.db.exists("DocType", "Desktop Icon") and frappe.db.exists("Desktop Icon", OLD_NAME):
		frappe.delete_doc("Desktop Icon", OLD_NAME, force=True, ignore_missing=True)
		print(f"[mypos_ws] Đã xóa Desktop Icon cũ {OLD_NAME}")
	if (
		frappe.db.exists("DocType", "Workspace Sidebar")
		and frappe.db.exists("Workspace Sidebar", NEW_SIDEBAR)
		and frappe.db.exists("Workspace Sidebar", OLD_NAME)
	):
		frappe.delete_doc("Workspace Sidebar", OLD_NAME, force=True, ignore_missing=True)
		print(f"[mypos_ws] Đã xóa Workspace Sidebar cũ {OLD_NAME}")


def _sync_module_sidebar():
	"""Frappe >= 16.50: Sidebar theo module. Bản < 16.50 không có DocType này -> bỏ qua."""
	if not frappe.db.exists("DocType", "Sidebar"):
		print("[mypos_ws] Không có DocType Sidebar (Frappe < 16.50): dùng workspace_sidebar/mypos.json")
		return
	path = _module_path("sidebar", "mypos", "mypos.json")
	if not os.path.exists(path):
		print(f"[mypos_ws] THIẾU file {path} -> bỏ qua sidebar")
		return
	expected = len(_load(path).get("items") or [])
	actual = frappe.db.count("Sidebar Item", {"parent": NEW_SIDEBAR, "parenttype": "Sidebar"})
	if not frappe.db.exists("Sidebar", NEW_SIDEBAR) or actual != expected:
		import_file_by_path(path, force=True)
		actual = frappe.db.count("Sidebar Item", {"parent": NEW_SIDEBAR, "parenttype": "Sidebar"})
		print(f"[mypos_ws] Sidebar {NEW_SIDEBAR}: import lại, {actual}/{expected} item")
	else:
		print(f"[mypos_ws] Sidebar {NEW_SIDEBAR}: khớp file ({actual} item)")
	for name in frappe.get_all(
		"Sidebar", filters={"module": MODULE, "standard": 0, "name": ["!=", NEW_SIDEBAR]}, pluck="name"
	):
		frappe.delete_doc("Sidebar", name, force=True, ignore_missing=True)
		print(f"[mypos_ws] Đã xóa Sidebar không chuẩn {name} (bản chuyển đổi tự động cũ)")


def execute():
	all_present = _sync_workspaces()
	_warn_custom_layers()
	if all_present and all(frappe.db.exists("Workspace", n) for n in WORKSPACES):
		_remove_old()
	else:
		print("[mypos_ws] Chưa đủ 4 workspace MYPOS -> GIỮ workspace / icon cũ")
	_sync_module_sidebar()
	frappe.clear_cache()
	frappe.db.commit()
