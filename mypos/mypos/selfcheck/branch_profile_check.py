def check_branch_profile(pos_profile=None):
	"""POS Profile phải có Branch + chọn profile xác định + /order lấy ảnh MYPOS Banner (2026-11-25).

	Dán CẢ hàm vào `bench --site <site> console` (SAU khi migrate) rồi gọi:
	    check_branch_profile("<POS Profile>")

	KHÔNG đụng chi nhánh / profile thật: tạo Branch tạm "ZZTEST BR <hash>", chép `pos_profile` thành 3 profile tạm
	(A, C ở Branch tạm 1; B ở Branch tạm 2; NB để thử thiếu Branch), user tạm zz.test.br.{u,v}@example.com (POS CASHIER), ca mở tạm
	(db_insert, bỏ qua hook), banner tạm. Cuối hàm ROLLBACK rồi dọn mọi dữ liệu "ZZTEST BR" / zz.test.br còn sót.
	Ca:
	  1  Lưu profile đang bật mà Branch trống -> chặn; đã tắt -> lưu được
	  2  Mỗi Branch tối đa 1 profile đang bật: profile thứ hai đang bật -> chặn (nêu tên profile kia); tắt -> lưu được;
	     bật lại -> chặn
	  3  User chỉ thuộc profile đang bật thiếu Branch -> resolve_pos_profile_name báo lỗi có tên profile
	  4  User thuộc A (Branch 1), B (Branch 2), không default -> A (tên A→Z); B default -> B
	  5  get_buzzers với profile thiếu Branch -> báo lỗi (không trả thẻ mọi chi nhánh)
	  6  _verify_sepay_signature: thiếu Branch / Branch chưa có secret / chữ ký sai -> 403 + Error Log đúng tiêu đề;
	     chữ ký đúng (secret của Branch) -> qua (2026-11-28, thay _verify_sepay_key)
	  7  _get_pos_profile(branch) có 2 profile đang bật (dữ liệu cũ, tạo bằng cờ self-test): không ca -> A; C mở ca -> C
	  8  /order _shop: banner public đầu tiên; ảnh private bị bỏ; get_brand_info không còn khóa "banner"
	"""
	if pos_profile is None:  # không truyền dữ liệu -> tự dựng quán thử tạm (selfcheck/test_shop.py), dọn ở cuối
		from mypos.selfcheck.test_shop import zz_test_shop

		_shop = zz_test_shop("create", open_shift=False)
		if not _shop.get("ok"):
			print(f"SKIP: {_shop.get('reason')}")
			print("KẾT QUẢ: SKIP")
			return None
		try:
			return check_branch_profile(_shop["pos_profile"])
		finally:
			zz_test_shop("drop", _shop["tag"])

	import traceback

	import frappe

	from mypos.mypos.api import customer_order_api as C
	from mypos.mypos.api import pos_api as P
	from mypos.mypos.doctype.branch_config import branch_config as BC
	from mypos.mypos.doctype.sepay import sepay as S

	# Dọn dữ liệu thử: QueryDeadlockError (MariaDB 1213 / 1020) -> rollback, chờ 1 giây, thử lại (tối đa 3 lần);
	# thành công -> commit ngay (bản ghi đã xóa không bị rollback lần thử sau cuốn mất). Lỗi khác ném lại cho khối gọi.
	DEADLOCK = getattr(frappe, "QueryDeadlockError", None) or getattr(frappe.exceptions, "QueryDeadlockError", ())

	def retry_deadlock(fn, *args, **kwargs):
		import time as _time

		for attempt in range(3):
			try:
				result = fn(*args, **kwargs)
				frappe.db.commit()
				return result
			except DEADLOCK:
				frappe.db.rollback()
				if attempt == 2:
					raise
				_time.sleep(1)

	PREFIX = "ZZTEST BR "
	USER_PREFIX = "zz.test.br"
	tag = frappe.generate_hash(length=5)
	results = []

	def ok(case, cond, extra=""):
		results.append((case, bool(cond)))
		print(f"{'PASS' if cond else 'FAIL'} {case} {extra}")

	def err_of(fn, *a, **kw):
		try:
			fn(*a, **kw)
			return None
		except Exception as e:  # noqa: BLE001
			frappe.clear_messages()
			return e

	def purge():
		frappe.db.rollback()
		frappe.set_user("Administrator")
		profiles = frappe.get_all("POS Profile", filters={"name": ["like", PREFIX + "%"]}, pluck="name")
		for p in profiles:
			retry_deadlock(frappe.db.delete, "POS Opening Entry", {"pos_profile": p})
			retry_deadlock(frappe.delete_doc, "POS Profile", p, force=1, ignore_permissions=True)
		for b in frappe.get_all("MYPOS Banner", filters={"title": ["like", PREFIX + "%"]}, pluck="name"):
			retry_deadlock(frappe.delete_doc, "MYPOS Banner", b, force=1, ignore_permissions=True)
		for u in frappe.get_all("User", filters={"name": ["like", USER_PREFIX + ".%"]}, pluck="name"):
			retry_deadlock(frappe.delete_doc, "User", u, force=1, ignore_permissions=True)
		for b in frappe.get_all("Branch", filters={"name": ["like", PREFIX + "%"]}, pluck="name"):
			retry_deadlock(frappe.delete_doc, "Branch", b, force=1, ignore_permissions=True)
		frappe.db.commit()
		return profiles

	def make_profile(suffix, branch, users=(), disabled=0, shared=False):
		prof = frappe.copy_doc(frappe.get_doc("POS Profile", pos_profile))
		if shared:  # giả lập dữ liệu cũ: 2 profile đang bật cùng Branch (bỏ qua quy tắc "1 profile / Branch")
			prof.flags.mypos_allow_shared_branch = True
		prof.set("__newname", f"{PREFIX}{suffix}-{tag}")
		prof.branch = branch
		prof.disabled = disabled
		prof.set("applicable_for_users", [])
		for u in users:
			prof.append("applicable_for_users", {"user": u, "default": 0})
		prof.insert(ignore_permissions=True)
		return prof

	def last_error_title():
		# Frappe v16: Error Log không có cột `title`; tiêu đề của log_error(title=...) nằm ở cột `method`.
		row = frappe.get_all("Error Log", filters={"method": ["like", "SePay webhook:%"]}, fields=["method"],
			order_by="creation desc", limit=1)
		return (row[0].method or "") if row else ""

	orig_profile = P._get_pos_profile
	old_req = getattr(frappe.local, "request", None)
	try:
		purge()
		frappe.set_user("Administrator")
		branch = frappe.get_doc({"doctype": "Branch", "branch": f"{PREFIX}{tag}"}).insert(ignore_permissions=True).name
		branch2 = frappe.get_doc({"doctype": "Branch", "branch": f"{PREFIX}{tag}-2"}).insert(ignore_permissions=True).name
		users = {}
		for k in ("u", "v"):
			email = f"{USER_PREFIX}.{k}.{tag}@example.com"
			frappe.get_doc({"doctype": "User", "email": email, "first_name": f"ZZTEST BR {k}", "user_type": "System User",
				"send_welcome_email": 0, "enabled": 1, "roles": [{"role": "POS CASHIER"}]}).insert(ignore_permissions=True)
			users[k] = email

		print("== 1. Chặn profile đang bật thiếu Branch ==")
		e = err_of(make_profile, "X", None)
		ok("1a Đang bật + Branch trống -> chặn", e and "chưa gán Chi nhánh" in str(e), f"-> {str(e)[:90]}" if e else "-> KHÔNG chặn")
		e = err_of(make_profile, "Y", None, disabled=1)
		ok("1b Đã tắt + Branch trống -> lưu được", e is None, f"({e})" if e else "")

		print("== 2. Mỗi Branch tối đa 1 profile đang bật ==")
		a = make_profile("A", branch, users=[users["v"]])
		e = err_of(make_profile, "B", branch, users=[users["v"]])
		ok("2a Profile thứ hai đang bật cùng Branch -> chặn, nêu tên A", e and a.name in str(e) and "chỉ được một POS Profile đang bật" in str(e),
			f"-> {str(e)[:110]}" if e else "-> KHÔNG chặn")
		e = err_of(make_profile, "B", branch, users=[users["v"]], disabled=1)
		ok("2b Đã tắt, cùng Branch -> lưu được", e is None, f"({e})" if e else "")
		b = frappe.get_doc("POS Profile", f"{PREFIX}B-{tag}")
		b.disabled = 0
		e = err_of(b.save, ignore_permissions=True)
		ok("2c Bật lại khi A còn bật -> chặn", e and a.name in str(e), f"-> {str(e)[:110]}" if e else "-> KHÔNG chặn")
		b = frappe.get_doc("POS Profile", b.name)
		b.branch, b.disabled = branch2, 0
		b.save(ignore_permissions=True)  # B sang Branch tạm 2 cho ca 4

		print("== 3. resolve_pos_profile_name: profile của user thiếu Branch ==")
		nb = make_profile("NB", branch, users=[users["u"]], shared=True)
		frappe.db.set_value("POS Profile", nb.name, "branch", None)  # dữ liệu cũ: bỏ qua validate
		frappe.set_user(users["u"])
		e = err_of(BC.resolve_pos_profile_name)
		frappe.set_user("Administrator")
		ok("3 Báo lỗi có tên profile NB, không rơi sang profile khác", e and nb.name in str(e) and "chưa được gán chi nhánh" in str(e),
			f"-> {str(e)[:110]}" if e else "-> KHÔNG lỗi")

		print("== 4. Thứ tự profile của user ==")
		frappe.set_user(users["v"])
		r1 = BC.resolve_pos_profile_name()
		frappe.set_user("Administrator")
		ok("4a Không default -> A (tên A→Z)", r1 == a.name, f"({r1})")
		frappe.db.set_value("POS Profile User", {"parent": b.name, "user": users["v"]}, "default", 1)
		frappe.set_user(users["v"])
		r2 = BC.resolve_pos_profile_name()
		frappe.set_user("Administrator")
		ok("4b B default -> B", r2 == b.name, f"({r2})")

		print("== 5. get_buzzers khi profile thiếu Branch ==")
		P._get_pos_profile = lambda branch_name=None: frappe._dict(name=nb.name, branch=None)
		e = err_of(P.get_buzzers)
		P._get_pos_profile = orig_profile
		ok("5 Báo lỗi, không trả thẻ mọi chi nhánh", e and "chưa được gán chi nhánh" in str(e), f"-> {str(e)[:90]}" if e else "-> KHÔNG lỗi")

		print("== 6. Webhook SePay: Error Log đúng lý do ==")
		from mypos.selfcheck.sepay_sign import webhook_request

		secret = "zzsecret-" + tag

		def verify_with(inv, sign_secret):
			frappe.local.request = webhook_request({"content": "ZZTEST"}, sign_secret)
			try:
				return err_of(lambda: S._verify_sepay_signature(inv, S._check_signature_headers()))
			finally:
				frappe.local.request = old_req

		cases = [
			("6a Thiếu Branch", frappe._dict(name="ZZTEST-INV", pos_profile=nb.name), "POS Profile thiếu Branch"),
			("6b Branch chưa có secret", frappe._dict(name="ZZTEST-INV", pos_profile=a.name), "Branch chưa cấu hình secret webhook"),
		]
		for case, inv, title in cases:
			e = verify_with(inv, secret)
			ok(case, isinstance(e, frappe.PermissionError) and title in last_error_title(), f"({type(e).__name__}, log: {last_error_title()})")
		bdoc = frappe.get_doc("Branch", branch)
		bdoc.sepay_webhook_secret = secret
		bdoc.save(ignore_permissions=True)
		inv = frappe._dict(name="ZZTEST-INV", pos_profile=a.name)
		e = verify_with(inv, "wrong-" + secret)
		ok("6c Chữ ký sai -> 403 + tiêu đề 'chữ ký sai'", isinstance(e, frappe.PermissionError) and "chữ ký sai" in last_error_title(),
			f"(log: {last_error_title()})")
		e = verify_with(inv, secret)
		ok("6d Chữ ký đúng -> qua", e is None, f"({e})" if e else "")

		print("== 7. Chọn profile của chi nhánh ==")
		c = make_profile("C", branch, shared=True)
		p1 = P._get_pos_profile(branch).name
		ok("7a Không ca nào mở -> A", p1 == a.name, f"({p1})")
		shift = frappe.get_doc({"doctype": "POS Opening Entry", "name": f"{PREFIX}SHIFT-{tag}", "pos_profile": c.name,
			"company": c.company, "user": users["v"], "status": "Open", "docstatus": 1,
			"period_start_date": frappe.utils.now_datetime(), "posting_date": frappe.utils.nowdate()})
		shift.db_insert()
		p2 = P._get_pos_profile(branch).name
		ok("7b C mở ca -> C", p2 == c.name, f"({p2})")
		frappe.db.delete("POS Opening Entry", {"name": shift.name})

		print("== 8. Ảnh đầu trang /order ==")
		def banner(title, image, sort):
			d = frappe.get_doc({"doctype": "MYPOS Banner", "title": f"{PREFIX}{title}", "image": image, "enabled": 1,
				"sort_order": sort, "pos_profile": a.name})
			d.name = f"{PREFIX}BNR-{title}-{tag}"
			d.db_insert()
		ok("8a Không banner của profile -> banner rỗng hoặc banner chung", "banner" in C._shop(branch))
		banner("private", f"/private/files/zztest-{tag}.jpg", -1000)
		banner("public", f"/files/zztest-{tag}.jpg", -999)
		shop = C._shop(branch)
		ok("8b Bỏ ảnh private, lấy ảnh public đầu tiên", shop["banner"] == f"/files/zztest-{tag}.jpg", f"({shop['banner']})")
		ok("8c get_brand_info không còn khóa banner", "banner" not in BC.get_brand_info(branch), f"({BC.get_brand_info(branch)})")
		ok("8d Custom Field Branch-brand_banner đã xóa", not frappe.db.exists("Custom Field", "Branch-brand_banner"))
	except Exception:
		ok("Lỗi ngoài dự kiến", False)
		traceback.print_exc()
	finally:
		P._get_pos_profile = orig_profile
		frappe.local.request = old_req
		try:
			left = purge()
			print(f"Đã dọn dữ liệu thử ({len(left)} profile tạm)")
		except Exception:  # noqa: BLE001
			print("WARN dọn dữ liệu lỗi — xóa tay POS Profile / Branch / User / MYPOS Banner bắt đầu bằng 'ZZTEST BR' / zz.test.br")
			traceback.print_exc()
		passed = sum(1 for _c, r in results if r)
		print(f"KẾT QUẢ: {passed}/{len(results)} PASS")
