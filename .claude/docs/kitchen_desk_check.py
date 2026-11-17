def check_kitchen_desk(cleanup=True):
	"""Kiểm tra POS KITCHEN vào Desk (desk_access = 1) và chặn API bán hàng theo role.

	Chạy trong `bench --site <site> console`: dán cả hàm rồi gọi check_kitchen_desk().
	Tự tạo 3 user tạm (mỗi người đúng 1 role POS, System User, không gán Customer), KHÔNG commit;
	cuối hàm rollback + xóa cache roles nên không để lại dữ liệu.
	Gọi API với tham số không hợp lệ: role đúng -> qua kiểm tra quyền rồi lỗi nghiệp vụ (không phải PermissionError);
	KITCHEN -> PermissionError ngay ở _require_sale_role. Không tạo đơn, không mở ca.
	"""
	import json

	import frappe
	from frappe.desk.desktop import get_desktop_page

	from leescoffee_pos.leescoffee_pos.api import pos_api as P

	ROLES = ("POS CASHIER", "POS KITCHEN", "POS MANAGER")
	SALE_MSG = "không có quyền thực hiện thao tác bán hàng"
	fails = []

	def ok(cond, msg):
		print(("OK   " if cond else "FAIL ") + msg)
		if not cond:
			fails.append(msg)

	def call(fn, *args, **kw):
		"""-> (loại lỗi | None, thông báo)."""
		try:
			fn(*args, **kw)
			return None, ""
		except Exception as e:  # noqa: BLE001
			frappe.clear_messages()
			return type(e).__name__, str(e)

	admin = frappe.session.user
	frappe.set_user("Administrator")
	users = {}
	try:
		print("== 1. desk_access 3 role ==")
		for role in ROLES:
			v = frappe.db.get_value("Role", role, "desk_access")
			print(f"INFO {role}: desk_access = {v}")
			ok(v is not None and int(v) == 1, f"{role} desk_access = 1")

		print("== 2. User tạm ==")
		for role in ROLES:
			email = f"zz.test.{role.lower().replace(' ', '.')}@example.com"
			if frappe.db.exists("User", email):
				frappe.delete_doc("User", email, force=1, ignore_permissions=True)
			frappe.get_doc({
				"doctype": "User", "email": email, "first_name": f"ZZTEST {role}",
				"user_type": "System User", "send_welcome_email": 0, "enabled": 1,
				"roles": [{"role": role}],
			}).insert(ignore_permissions=True)
			users[role] = email
			ut = frappe.db.get_value("User", email, "user_type")
			pos_roles = [r for r in frappe.get_roles(email) if r.startswith("POS ")]
			print(f"INFO {email}: user_type = {ut}, roles = {pos_roles}")
			ok(ut == "System User", f"{role}: user_type = System User (vào được /desk)")

		print("== 3. KITCHEN vào workspace leescoffee_pos ==")
		k = users["POS KITCHEN"]
		frappe.set_user(k)
		try:
			err, msg = call(get_desktop_page, json.dumps({"name": "leescoffee_pos", "title": "leescoffee_pos"}))
			ok(err is None, f"get_desktop_page('leescoffee_pos') bằng {k} thành công" + (f" — lỗi {err}: {msg}" if err else ""))
			cfg_err, _m = call(P.get_pos_config)
			nav = None if cfg_err else P.get_pos_config().get("nav")
			ok(nav == ["kitchen"], f"get_pos_config nav = {nav} (bấm POS -> /pos/kitchen)")
		finally:
			frappe.set_user("Administrator")

		print("== 4. API bán hàng theo role ==")
		cases = [
			("create_draft_order", P.create_draft_order, ([], "Take Away")),
			("pay_cash", P.pay_cash, ("ZZTEST-KHONG-CO",)),
			("cancel_draft_order", P.cancel_draft_order, ("ZZTEST-KHONG-CO",)),
		]
		for role in ROLES:
			u = users[role]
			frappe.set_user(u)
			try:
				for name, fn, args in cases:
					err, msg = call(fn, *args)
					blocked = err == "PermissionError" and SALE_MSG in msg
					if role == "POS KITCHEN":
						ok(blocked, f"KITCHEN gọi {name} -> bị chặn ({err}: {msg[:80]})")
					else:
						ok(not blocked, f"{role.split()[1]} gọi {name} -> qua kiểm tra quyền (lỗi nghiệp vụ mong đợi: {err}: {msg[:60]})")
			finally:
				frappe.set_user("Administrator")
	finally:
		frappe.set_user("Administrator")
		frappe.db.rollback()
		for u in users.values():
			frappe.clear_cache(user=u)
		if cleanup:
			left = [u for u in users.values() if frappe.db.exists("User", u)]
			for u in left:
				frappe.delete_doc("User", u, force=1, ignore_permissions=True)
			if left:
				frappe.db.commit()
				print(f"WARN có commit ngầm, đã xóa user tạm: {left}")
			else:
				print("Đã rollback: không còn user tạm")
		frappe.set_user(admin)

	print("== KẾT QUẢ:", "PASS" if not fails else f"FAIL ({len(fails)})", "==")
	return fails
