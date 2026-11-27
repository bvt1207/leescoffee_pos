def check_apps_screen():
	"""Ô MYPOS trên màn Apps của Desk (hook `add_to_apps_screen`, Frappe 16.61). CHỈ ĐỌC, không tạo / sửa / xóa dữ liệu.

	Chạy SAU migrate (hooks mới cần `bench restart` / khởi động lại `bench start` để web server nạp):
	    bench --site <site> execute mypos.selfcheck.apps_screen_check.check_apps_screen

	Dùng user CÓ SẴN trên site (mỗi role POS / System Manager lấy 1 user đang bật, không phải Administrator) + Administrator
	+ Guest + (nếu có) 1 System User không có role POS / System Manager. Thiếu user cho role nào -> SKIP role đó.
	Kiểm cho từng user (frappe.set_user tạm, cuối hàm trả lại user cũ):
	- `has_app_permission()` đúng theo role; `frappe.apps.get_apps()` có đúng MỘT ô "mypos" (hoặc không có ô nào);
	- `frappe.boot.get_app_data()`: mục mypos `on_apps_screen` đúng, `app_route` trống (để client đi theo landing ladder);
	- điểm đến khi bấm ô (server mô phỏng `app_landing_route`: app không có Dock -> mục đầu tiên của Sidebar "MYPOS" đã lọc
	  theo quyền, `get_module_landing_route`) = workspace đầu tiên trong Sidebar mà user được xem.
	"""
	import os

	import frappe

	APP = "mypos"
	SIDEBAR = "MYPOS"
	POS_ROLES = ("POS CASHIER", "POS KITCHEN", "POS MANAGER", "System Manager")
	LOGO = "/assets/mypos/images/logo.svg"

	results = []
	original_user = frappe.session.user

	def ok(cond, label, detail=""):
		results.append(bool(cond))
		print(f"{'PASS' if cond else 'FAIL'} {label}" + (f" — {detail}" if detail and not cond else ""))

	def clear_request_cache():
		# get_apps / get_docked_apps dùng @request_cache (theo request, không theo user) -> xóa giữa các lần đổi user.
		cache = getattr(frappe.local, "request_cache", None)
		if cache is not None and hasattr(cache, "clear"):
			cache.clear()

	def user_with_role(role):
		rows = frappe.db.sql(
			"""SELECT hr.parent FROM `tabHas Role` hr JOIN `tabUser` u ON u.name = hr.parent
			WHERE hr.parenttype = 'User' AND hr.role = %s AND u.enabled = 1 AND u.user_type = 'System User'
			AND u.name NOT IN ('Administrator', 'Guest') ORDER BY u.creation LIMIT 1""",
			role,
		)
		return rows[0][0] if rows else None

	def user_without_roles():
		rows = frappe.db.sql(
			"""SELECT u.name FROM `tabUser` u WHERE u.enabled = 1 AND u.user_type = 'System User'
			AND u.name NOT IN ('Administrator', 'Guest')
			AND NOT EXISTS (SELECT 1 FROM `tabHas Role` hr WHERE hr.parent = u.name AND hr.parenttype = 'User'
				AND hr.role IN %(roles)s)
			ORDER BY u.creation LIMIT 1""",
			{"roles": POS_ROLES},
		)
		return rows[0][0] if rows else None

	def expected_landing(user):
		"""Workspace đầu tiên (theo thứ tự Sidebar) có role trùng role của user."""
		if not frappe.db.exists("Sidebar", SIDEBAR):
			return None
		roles = set(frappe.get_roles(user))
		for row in frappe.get_doc("Sidebar", SIDEBAR).items:
			if row.type == "Link" and row.link_type == "Workspace":
				ws_roles = set(frappe.get_all("Has Role", filters={"parent": row.link_to, "parenttype": "Workspace"}, pluck="role"))
				if user == "Administrator" or not ws_roles or ws_roles & roles:
					return "/desk/" + frappe.utils.slug(row.link_to)
		return None

	def actual_landing(user):
		from frappe.desk.doctype.sidebar.sidebar import get_module_landing_route, resolve_sidebar

		resolved = resolve_sidebar(SIDEBAR, user)
		if not resolved:
			return None
		return get_module_landing_route(resolved.as_boot_entry().get("items") or [])

	try:
		hooks = frappe.get_hooks("add_to_apps_screen", app_name=APP)
		ok(len(hooks) == 1, "hook add_to_apps_screen: đúng 1 mục", f"{hooks}")
		hook = hooks[0] if hooks else {}
		ok(hook.get("name") == APP and hook.get("title") == "MYPOS", "hook: name = mypos, title = MYPOS", f"{hook}")
		ok(hook.get("logo") == LOGO, f"hook: logo = {LOGO}", f"{hook.get('logo')!r}")
		ok(not hook.get("route"), "hook: không khai route (điểm đến theo Sidebar đã lọc quyền)", f"{hook.get('route')!r}")
		ok(hook.get("has_permission") == "mypos.permissions.has_app_permission", "hook: has_permission = mypos.permissions.has_app_permission")
		logo_file = frappe.get_app_path(APP, "public", "images", "logo.svg")
		ok(os.path.isfile(logo_file), f"file logo có thật: {logo_file}")

		from frappe.apps import get_apps
		from frappe.boot import get_app_data

		from mypos.permissions import has_app_permission

		cases = []  # (nhãn, user, mong đợi thấy ô)
		for role in POS_ROLES:
			u = user_with_role(role)
			if u:
				cases.append((role, u, True))
			else:
				print(f"SKIP {role}: không có user đang bật có role này")
		cases.append(("Administrator", "Administrator", True))
		cases.append(("Guest", "Guest", False))
		u = user_without_roles()
		if u:
			cases.append(("không role POS / System Manager", u, False))
		else:
			print("SKIP user không role POS: không có System User nào như vậy")

		for label, user, expect in cases:
			print(f"== {label}: {user}")
			frappe.set_user(user)
			clear_request_cache()
			try:
				ok(has_app_permission() is expect, f"{label}: has_app_permission() = {expect}")
				tiles = [a for a in get_apps() if a.get("name") == APP]
				ok(len(tiles) == (1 if expect else 0), f"{label}: get_apps() có {1 if expect else 0} ô MYPOS", f"{tiles}")
				entry = next((a for a in get_app_data() if a.get("app_name") == APP), None)
				ok(entry is not None and bool(entry.get("on_apps_screen")) is expect,
					f"{label}: app_data.on_apps_screen = {expect}", f"{entry and entry.get('on_apps_screen')!r}")
				if expect and entry is not None:
					ok(not entry.get("app_route"), f"{label}: app_data.app_route trống", f"{entry.get('app_route')!r}")
					got, want = actual_landing(user), expected_landing(user)
					ok(got and got == want, f"{label}: bấm ô MYPOS -> {got}", f"mong đợi {want}")
			finally:
				frappe.set_user(original_user)
				clear_request_cache()
	finally:
		frappe.set_user(original_user)
		print(f"KẾT QUẢ: {sum(results)}/{len(results)} PASS")
