def check_desktop_icons():
	"""Desktop Icon của app MYPOS (Frappe 16.61). CHỈ ĐỌC, không tạo / sửa / xóa dữ liệu.

	Chạy SAU migrate:
	    bench --site <site> execute mypos.selfcheck.desktop_icon_check.check_desktop_icons
	Icon được nạp từ `mypos/desktop_icon/*.json` bằng `import_desktop_icon_fixtures` CHỈ khi site ở chế độ lưới icon
	(`is_desktop_icons_page()`); site ở chế độ Apps không có dòng icon nào -> các ý "tồn tại" FAIL kèm INFO chế độ.
	Kiểm từng icon trong file: tồn tại trong DB; app = mypos; roles đúng bảng EXPECTED_ROLES (và khớp file); link_type hợp lệ;
	External -> link `/desk/<workspace>` trỏ Workspace có thật, link `/pos/...` thuộc route của app;
	Workspace Sidebar -> `sidebar` / `link_to` tồn tại; `parent_icon` (nếu có) tồn tại. Thêm: icon khác cùng nhãn "MYPOS%" trong DB.
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
	LINK_TYPES = ("External", "Workspace Sidebar")

	results = []

	def ok(cond, label, detail=""):
		results.append(bool(cond))
		print(f"{'PASS' if cond else 'FAIL'} {label}" + (f" — {detail}" if detail and not cond else ""))

	try:
		try:
			from frappe.desk.doctype.desktop_icon.desktop_icon import is_desktop_icons_page

			print(f"INFO is_desktop_icons_page() = {is_desktop_icons_page()}")
		except Exception as e:  # noqa: BLE001
			print(f"INFO không gọi được is_desktop_icons_page(): {e!r}")

		icon_dir = frappe.get_app_path(APP, "desktop_icon")
		files = sorted(f for f in os.listdir(icon_dir) if f.endswith(".json")) if os.path.isdir(icon_dir) else []
		ok(files, f"app có file Desktop Icon ở {icon_dir}", "không có file")
		labels_in_files = set()
		ws_by_slug = {frappe.scrub(w).replace("_", "-"): w for w in frappe.get_all("Workspace", pluck="name")}

		for fn in files:
			data = json.load(open(os.path.join(icon_dir, fn), encoding="utf-8"))
			name = data.get("name") or data.get("label")
			labels_in_files.add(name)
			print(f"== {name} ({fn})")
			ok(name in EXPECTED_ROLES, f"{name}: thuộc danh sách icon mong đợi", f"{sorted(EXPECTED_ROLES)}")
			file_roles = {r.get("role") for r in data.get("roles", [])}
			ok(file_roles == EXPECTED_ROLES.get(name), f"{name}: roles trong file đúng", f"file {sorted(file_roles)}")
			if not frappe.db.exists("Desktop Icon", name):
				ok(False, f"{name}: tồn tại trong DB", "chưa nạp (site ở chế độ Apps? xem INFO ở trên)")
				continue
			ok(True, f"{name}: tồn tại trong DB")
			icon = frappe.get_doc("Desktop Icon", name)
			ok(icon.app == APP, f"{name}: app = {APP}", f"thực tế {icon.app!r}")
			db_roles = {r.role for r in (icon.get("roles") or [])}
			ok(db_roles == EXPECTED_ROLES.get(name), f"{name}: roles trong DB đúng", f"DB {sorted(db_roles)}")
			ok(icon.link_type in LINK_TYPES, f"{name}: link_type hợp lệ", f"{icon.link_type!r}")
			if icon.link_type == "External":
				link = (icon.link or "").rstrip("/")
				if link.startswith("/desk/"):
					slug = link[len("/desk/"):]
					ok(slug in ws_by_slug, f"{name}: {link} trỏ Workspace có thật", "không có Workspace khớp")
				else:
					ok(link in POS_ROUTES, f"{name}: {link} là route của app", f"route hợp lệ: {POS_ROUTES}")
			else:
				ok(not icon.get("sidebar") or frappe.db.exists("Workspace Sidebar", icon.sidebar),
					f"{name}: sidebar tồn tại", f"{icon.get('sidebar')!r}")
				ok(not icon.get("link_to") or frappe.db.exists("Workspace Sidebar", icon.link_to),
					f"{name}: link_to tồn tại", f"{icon.get('link_to')!r}")
			ok(not icon.get("parent_icon") or frappe.db.exists("Desktop Icon", icon.parent_icon),
				f"{name}: parent_icon tồn tại (nếu có)", f"{icon.get('parent_icon')!r}")

		others = [
			r for r in frappe.get_all("Desktop Icon", filters={"label": ["like", "MYPOS%"]}, fields=["name", "app", "standard"])
			if r.name not in labels_in_files
		]
		ok(not others, "không có Desktop Icon MYPOS nào khác ngoài file của app", f"{others}")
	finally:
		print(f"KẾT QUẢ: {sum(results)}/{len(results)} PASS")
