def check_desktop_icons():
	"""Desktop Icon của app MYPOS (Frappe 16.61). CHỈ ĐỌC, không tạo / sửa / xóa dữ liệu.

	Chạy SAU migrate:
	    bench --site <site> execute mypos.selfcheck.desktop_icon_check.check_desktop_icons

	Frappe 16.61 (đã đối chiếu mã): icon được nạp từ `<app>/<app>/desktop_icon/*.json` (`get_app_level_directory_path`)
	bằng `import_desktop_icon_fixtures`, CHỈ khi Desktop Settings → Desktop Page = "Desktop Icons" (`is_desktop_icons_page()`).
	Mặc định "Apps": site không có dòng Desktop Icon nào -> các ý kiểm trong DB được SKIP (không tính FAIL).

	Luôn kiểm (theo file): roles đúng EXPECTED_ROLES; link `/desk/<workspace>` trỏ Workspace có thật, link `/pos/...` là route
	của app; không dùng `sidebar` / `link_to` (Workspace Sidebar là kho lưu không dùng).
	Chế độ lưới icon: icon tồn tại trong DB, app = mypos, roles trong DB đúng, `parent_icon` (nếu có) tồn tại,
	không có Desktop Icon "MYPOS%" nào khác ngoài file của app.
	"""
	import json
	import os

	import frappe

	APP = "mypos"
	EXPECTED_ROLES = {
		"MYPOS Cashier": {"POS CASHIER", "System Manager"},
		"MYPOS Kitchen": {"POS KITCHEN", "System Manager"},
		"MYPOS Manager": {"POS MANAGER", "System Manager"},
		"MYPOS Admin": {"System Manager"},
	}
	POS_ROUTES = ("/pos", "/pos/orders", "/pos/kitchen", "/pos/customer", "/pos/status")

	results = []

	def ok(cond, label, detail=""):
		results.append(bool(cond))
		print(f"{'PASS' if cond else 'FAIL'} {label}" + (f" — {detail}" if detail and not cond else ""))

	try:
		grid = False
		try:
			from frappe.desk.doctype.desktop_settings.desktop_settings import get_desktop_page, is_desktop_icons_page

			grid = bool(is_desktop_icons_page())
			print(f"INFO Desktop Settings → Desktop Page = {get_desktop_page()!r} (lưới icon: {grid})")
		except Exception as e:  # noqa: BLE001
			print(f"INFO không đọc được chế độ desktop: {e!r} — coi như Apps")
		if not grid:
			print("SKIP kiểm Desktop Icon trong DB: site ở chế độ Apps, Frappe không nạp icon (xem docs/rules/workspace.md)")

		icon_dir = frappe.get_app_path(APP, "desktop_icon")
		files = sorted(f for f in os.listdir(icon_dir) if f.endswith(".json")) if os.path.isdir(icon_dir) else []
		ok(files, f"app có file Desktop Icon ở {icon_dir}", "không có file")
		labels_in_files = set()
		ws_by_slug = {frappe.scrub(w).replace("_", "-"): w for w in frappe.get_all("Workspace", pluck="name")}

		def check_link(name, link_type, link):
			ok(link_type == "External", f"{name}: link_type = External", f"{link_type!r}")
			link = (link or "").rstrip("/")
			if link.startswith("/desk/"):
				ok(link[len("/desk/"):] in ws_by_slug, f"{name}: {link} trỏ Workspace có thật", "không có Workspace khớp")
			else:
				ok(link in POS_ROUTES, f"{name}: {link} là route của app", f"route hợp lệ: {POS_ROUTES}")

		for fn in files:
			data = json.load(open(os.path.join(icon_dir, fn), encoding="utf-8"))
			name = data.get("name") or data.get("label")
			labels_in_files.add(name)
			print(f"== {name} ({fn})")
			ok(name in EXPECTED_ROLES, f"{name}: thuộc danh sách icon mong đợi", f"{sorted(EXPECTED_ROLES)}")
			file_roles = {r.get("role") for r in data.get("roles", [])}
			ok(file_roles == EXPECTED_ROLES.get(name), f"{name}: roles trong file đúng", f"file {sorted(file_roles)}")
			ok(data.get("app") == APP, f"{name}: app trong file = {APP}", f"{data.get('app')!r}")
			ok(not data.get("sidebar") and not data.get("link_to"), f"{name}: không trỏ Workspace Sidebar (sidebar / link_to trống)")
			check_link(name, data.get("link_type"), data.get("link"))
			if not grid:
				continue
			if not frappe.db.exists("Desktop Icon", name):
				ok(False, f"{name}: tồn tại trong DB", "chưa nạp: chạy `bench --site <site> sync-desktop-icons`")
				continue
			icon = frappe.get_doc("Desktop Icon", name)
			ok(icon.app == APP, f"{name}: app trong DB = {APP}", f"{icon.app!r}")
			db_roles = {r.role for r in (icon.get("roles") or [])}
			ok(db_roles == EXPECTED_ROLES.get(name), f"{name}: roles trong DB đúng", f"DB {sorted(db_roles)}")
			ok(not icon.get("parent_icon") or frappe.db.exists("Desktop Icon", icon.parent_icon),
				f"{name}: parent_icon tồn tại (nếu có)", f"{icon.get('parent_icon')!r}")

		if grid:
			others = [
				r for r in frappe.get_all("Desktop Icon", filters={"label": ["like", "MYPOS%"]}, fields=["name", "icon_type"])
				if r.name not in labels_in_files
			]
			ok(not others, "không có Desktop Icon MYPOS nào khác ngoài file của app", f"{others}")
	finally:
		print(f"KẾT QUẢ: {sum(results)}/{len(results)} PASS")
