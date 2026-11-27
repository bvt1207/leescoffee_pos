def check_apps_screen_roles():
	"""Ô MYPOS trên màn Apps theo role, bằng USER TẠM (không cần dữ liệu quán). Ghi user tạm rồi dọn.

	    bench --site <site> execute mypos.selfcheck.apps_screen_roles_check.check_apps_screen_roles

	Tạo user tạm zz.test.apps.<n>@example.com (System User, không gửi email) với đúng các role dưới, KHÔNG commit;
	cuối hàm rollback + xóa cache; user nào lỡ bị commit (commit ngầm) thì xóa có thử lại khi deadlock, còn sót in WARN.
	Kiểm cho từng user (frappe.set_user tạm): has_app_permission(); get_apps() có 1 / 0 ô "mypos"; app_data.on_apps_screen;
	điểm đến khi bấm ô = mục đầu tiên của Sidebar "MYPOS" sau khi lọc quyền (server mô phỏng client `app_landing_route`:
	`resolve_sidebar` + `get_module_landing_route`). Sidebar xếp Admin, Manager, Cashier, Kitchen nên:
	  System Manager / Administrator -> /desk/mypos-admin; POS MANAGER -> /desk/mypos-manager;
	  POS CASHIER -> /desk/mypos-cashier; POS KITCHEN -> /desk/mypos-kitchen; CASHIER + MANAGER -> /desk/mypos-manager;
	  không role POS / Guest -> không có ô.
	Workspace MYPOS Admin chỉ có role System Manager -> user chỉ POS MANAGER không thấy nó (Workspace.is_permitted).
	"""
	import time

	import frappe

	APP = "mypos"
	SIDEBAR = "MYPOS"
	PREFIX = "zz.test.apps"
	# (nhãn, roles, thấy ô?, điểm đến mong đợi)
	CASES = [
		("POS CASHIER", ["POS CASHIER"], True, "/desk/mypos-cashier"),
		("POS KITCHEN", ["POS KITCHEN"], True, "/desk/mypos-kitchen"),
		("POS MANAGER", ["POS MANAGER"], True, "/desk/mypos-manager"),
		("System Manager", ["System Manager"], True, "/desk/mypos-admin"),
		("CASHIER + MANAGER", ["POS CASHIER", "POS MANAGER"], True, "/desk/mypos-manager"),
		("không role POS", [], False, None),
	]
	DEADLOCK = getattr(frappe, "QueryDeadlockError", None) or getattr(frappe.exceptions, "QueryDeadlockError", ())

	results = []
	original_user = frappe.session.user
	made = []

	def ok(cond, label, detail=""):
		results.append(bool(cond))
		print(f"{'PASS' if cond else 'FAIL'} {label}" + (f" — {detail}" if detail and not cond else ""))

	def retry_deadlock(fn, *args, **kwargs):
		for attempt in range(3):
			try:
				result = fn(*args, **kwargs)
				frappe.db.commit()
				return result
			except DEADLOCK:
				frappe.db.rollback()
				if attempt == 2:
					raise
				time.sleep(1)

	def clear_request_cache():
		cache = getattr(frappe.local, "request_cache", None)
		if cache is not None and hasattr(cache, "clear"):
			cache.clear()

	def landing(user):
		from frappe.desk.doctype.sidebar.sidebar import get_module_landing_route, resolve_sidebar

		resolved = resolve_sidebar(SIDEBAR, user)
		return get_module_landing_route(resolved.as_boot_entry().get("items") or []) if resolved else None

	def probe(label, user, expect_tile, expect_route):
		from frappe.apps import get_apps
		from frappe.boot import get_app_data

		from mypos.permissions import has_app_permission

		print(f"== {label}: {user}")
		frappe.set_user(user)
		clear_request_cache()
		try:
			ok(has_app_permission() is expect_tile, f"{label}: has_app_permission() = {expect_tile}")
			tiles = [a for a in get_apps() if a.get("name") == APP]
			ok(len(tiles) == (1 if expect_tile else 0), f"{label}: get_apps() có {1 if expect_tile else 0} ô MYPOS", f"{tiles}")
			entry = next((a for a in get_app_data() if a.get("app_name") == APP), None)
			ok(entry is not None and bool(entry.get("on_apps_screen")) is expect_tile,
				f"{label}: app_data.on_apps_screen = {expect_tile}", f"{entry and entry.get('on_apps_screen')!r}")
			if expect_tile:
				got = landing(user)
				ok(got == expect_route, f"{label}: bấm ô MYPOS -> {expect_route}", f"thực tế {got}")
		finally:
			frappe.set_user(original_user)
			clear_request_cache()

	try:
		if not frappe.db.exists("Sidebar", SIDEBAR):
			print("SKIP: chưa có Sidebar MYPOS (chưa migrate?)")
			print("KẾT QUẢ: SKIP")
			return None
		frappe.set_user("Administrator")
		tag = frappe.generate_hash(length=6).lower()
		for i, (label, roles, expect_tile, expect_route) in enumerate(CASES, 1):
			email = f"{PREFIX}.{tag}.{i}@example.com"
			user = frappe.get_doc({
				"doctype": "User", "email": email, "first_name": f"ZZTEST {label}", "send_welcome_email": 0,
				"enabled": 1, "user_type": "System User", "roles": [{"role": r} for r in roles],
			})
			user.flags.no_welcome_mail = True
			user.insert(ignore_permissions=True)
			made.append(email)
		for i, (label, _roles, expect_tile, expect_route) in enumerate(CASES):
			probe(label, made[i], expect_tile, expect_route)
		probe("Administrator", "Administrator", True, "/desk/mypos-admin")
		probe("Guest", "Guest", False, None)
	except Exception as e:  # noqa: BLE001
		ok(False, "Lỗi ngoài dự kiến", repr(e)[:200])
		import traceback

		traceback.print_exc()
	finally:
		frappe.set_user(original_user)
		frappe.db.rollback()
		for email in made:
			frappe.clear_cache(user=email)
		left = [u for u in made if frappe.db.exists("User", u)]
		failed = []
		for u in left:
			try:
				for c in frappe.get_all("Contact", filters={"user": u}, pluck="name"):
					retry_deadlock(frappe.delete_doc, "Contact", c, force=1, ignore_permissions=True)
				retry_deadlock(frappe.delete_doc, "User", u, force=1, ignore_permissions=True)
			except Exception as e:  # noqa: BLE001
				frappe.db.rollback()
				failed.append(f"{u}: {str(e)[:100]}")
		if left:
			print(f"WARN có commit ngầm, đã xóa user tạm: {[u for u in left if not frappe.db.exists('User', u)]}")
		if failed:
			print(f"WARN chưa xóa được (xóa tay trên Desk → User, lọc '{PREFIX}'): {failed}")
		print(f"KẾT QUẢ: {sum(results)}/{len(results)} PASS")
