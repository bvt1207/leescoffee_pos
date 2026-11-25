def check_poll_load(pos_profile, item_code, mode_of_payment, price_list=None, rounds=20):
	"""Giảm tải poll (2026-11-25, giai đoạn 1 + 2): phiên bản thay đổi theo POS Profile (change_feed.py + get_pos_changes),
	Pha chế chỉ đơn của profile user thuộc về (D1), get_orders_shift, bỏ N+1 số thẻ bàn. In thêm số truy vấn SQL + thời gian
	mỗi API để so trước / sau.

	Dán CẢ hàm vào `bench --site <site> console` MỚI (SAU khi migrate + restart) rồi gọi, ví dụ:
	    check_poll_load("POS TEST", "CH-CFLON", "Cash", price_list="<Price List của MYPOS Menu>")

	KHÔNG đụng ca / đơn / thẻ thật: chép POS Profile thành 2 profile "ZZTEST Poll ..." (A, M, K ở profile 1; B ở profile 2),
	user tạm A, B (POS CASHIER), K, K2 (POS KITCHEN; K2 không thuộc profile nào), M (POS MANAGER), 1 thẻ bàn tạm "ZZP-...".
	Cuối hàm dọn mọi dữ liệu thử + khóa Redis phiên bản của profile tạm; dòng KẾT QUẢ luôn được in.
	"""
	import time
	import traceback

	import frappe
	from frappe.utils import now_datetime, nowdate

	from leescoffee_pos.leescoffee_pos.api import pos_api as P
	from leescoffee_pos.leescoffee_pos.doctype.pos_invoice_hooks import change_feed as CF

	PREFIX = "zz.test.poll"
	PROFILE_PREFIX = "ZZTEST Poll "
	WALK_IN_PREFIX = "ZZTEST WI Poll "
	CARD_PREFIX = "ZZP-"
	ROLE_OF = {"A": "POS CASHIER", "B": "POS CASHIER", "K": "POS KITCHEN", "K2": "POS KITCHEN", "M": "POS MANAGER"}
	DEADLOCK = getattr(frappe, "QueryDeadlockError", None) or getattr(frappe.exceptions, "QueryDeadlockError", ())
	results, users, ctx = [], {}, {"profiles": []}

	def ok(case, cond, extra=""):
		results.append((case, bool(cond)))
		print(f"{'PASS' if cond else 'FAIL'} {case} {extra}")

	def as_user(key, fn, *args, **kw):
		frappe.set_user(users[key])
		try:
			return fn(*args, **kw), None
		except Exception as e:  # noqa: BLE001
			frappe.clear_messages()
			return None, e
		finally:
			frappe.set_user("Administrator")

	def blocked(case, err, *phrases):
		text = str(err or "").lower()
		ok(case, err is not None and all(ph.lower() in text for ph in phrases),
			f"-> {type(err).__name__}: {str(err)[:160]}" if err else "-> KHÔNG bị chặn")

	# ---------------- dọn dữ liệu thử ----------------
	def delete_fresh(dt, name, removed, failed, cancel=False):
		last = None
		for _attempt in range(3):
			try:
				frappe.db.commit()
				if not frappe.db.exists(dt, name):
					return
				doc = frappe.get_doc(dt, name)
				if cancel and doc.docstatus == 1:
					doc.flags.ignore_permissions = True
					doc.cancel()
				frappe.delete_doc(dt, name, force=1, ignore_permissions=True)
				frappe.db.commit()
				removed.append(f"{dt} {name}")
				return
			except DEADLOCK as ex:
				last = ex
				frappe.db.rollback()
				time.sleep(1)
			except Exception as ex:  # noqa: BLE001
				frappe.db.rollback()
				frappe.clear_messages()
				failed.append((dt, name, f"{type(ex).__name__}: {str(ex)[:150]}"))
				return
		failed.append((dt, name, f"{type(last).__name__} sau 3 lần thử: {str(last)[:150]}"))

	def purge_leftovers():
		removed, failed = [], []
		try:
			frappe.db.commit()
			for prof in frappe.get_all("POS Profile", filters={"name": ["like", PROFILE_PREFIX + "%"]}, pluck="name"):
				for dt in ("POS Invoice", "POS Opening Entry"):
					for n in frappe.get_all(dt, filters={"pos_profile": prof}, pluck="name"):
						delete_fresh(dt, n, removed, failed, cancel=True)
				delete_fresh("POS Profile", prof, removed, failed)
				frappe.cache.delete(frappe.cache.make_key(CF.COUNTER_PREFIX + prof))
			for card in frappe.get_all("MYPOS Buzzer", filters={"buzzer_number": ["like", CARD_PREFIX + "%"]}, pluck="name"):
				delete_fresh("MYPOS Buzzer", card, removed, failed)
			for c in frappe.get_all("Customer", filters={"customer_name": ["like", WALK_IN_PREFIX + "%"]}, pluck="name"):
				for n in frappe.get_all("POS Invoice", filters={"customer": c}, pluck="name"):
					delete_fresh("POS Invoice", n, removed, failed, cancel=True)
				delete_fresh("Customer", c, removed, failed)
			contacts = set(frappe.get_all("Contact", filters={"user": ["like", PREFIX + ".%"]}, pluck="name"))
			contacts |= set(frappe.get_all("Contact", filters={"email_id": ["like", PREFIX + ".%"]}, pluck="name"))
			for c in sorted(contacts):
				delete_fresh("Contact", c, removed, failed)
			for u in frappe.get_all("User", filters={"name": ["like", PREFIX + ".%"]}, pluck="name"):
				frappe.clear_cache(user=u)
				frappe.cache.delete_value(CF.PROFILE_CACHE_PREFIX + u)
				for nl in frappe.get_all("Notification Log", filters={"for_user": u}, pluck="name"):
					delete_fresh("Notification Log", nl, removed, failed)
				delete_fresh("User", u, removed, failed)
		except Exception as ex:  # noqa: BLE001
			frappe.db.rollback()
			failed.append(("(quét dữ liệu thử)", "", f"{type(ex).__name__}: {str(ex)[:150]}"))
		return removed, failed

	def report_cleanup(removed, failed, stage):
		if removed:
			print(f"WARN [{stage}] đã xóa dữ liệu thử còn trong DB: {len(removed)} bản ghi")
		for dt, name, why in failed:
			print(f"WARN [{stage}] KHÔNG dọn được {dt} {name}: {why}")
			if name:
				print(f'     Xóa tay (bench console): frappe.delete_doc("{dt}", "{name}", force=1, ignore_permissions=True); frappe.db.commit()')

	# ---------------- thao tác thử ----------------
	def draft(key="A", order_type="Take Away", buzzer=None):
		line = [{"item_code": item_code, "qty": 1, "options": []}]
		res, err = as_user(key, P.create_draft_order, line, order_type, mode_of_payment=mode_of_payment,
			price_list=ctx["price_list"], buzzer=buzzer)
		if err:
			raise err
		return res["invoice_name"]

	def paid(key="A", order_type="Take Away", buzzer=None):
		name = draft(key, order_type, buzzer)
		_r, err = as_user(key, P.pay_cash, name)
		if err:
			raise err
		return name

	def ver(profile):
		return CF.get_version(profile)

	def changed(case, profile, fn):
		before = ver(profile)
		fn()
		after = ver(profile)
		ok(case, after != before, f"({before} -> {after})")

	def measure(label, key, fn, *args):
		"""Trung bình thời gian + số truy vấn SQL của MỘT lần gọi (không tính set_user)."""
		frappe.set_user(users[key])
		orig = frappe.db.sql
		count = {"n": 0}

		def counted(*a, **kw):
			count["n"] += 1
			return orig(*a, **kw)

		total, err = 0.0, None
		try:
			frappe.db.sql = counted
			for _i in range(rounds):
				t0 = time.perf_counter()
				try:
					fn(*args)
				except Exception as e:  # noqa: BLE001
					err = e
					frappe.clear_messages()
				total += time.perf_counter() - t0
		finally:
			frappe.db.sql = orig
			frappe.set_user("Administrator")
		q, ms = count["n"] / rounds, total * 1000 / rounds
		print(f"INFO {label:<28} {ms:7.1f} ms  {q:5.1f} SQL/lần" + (f"  LỖI {type(err).__name__}: {str(err)[:80]}" if err else ""))
		return q, ms, err

	admin = frappe.session.user
	frappe.set_user("Administrator")
	try:
		print("== 0. Dọn dữ liệu thử còn sót ==")
		removed0, failed0 = purge_leftovers()
		report_cleanup(removed0, failed0, "đầu")
		if failed0:
			raise RuntimeError("Còn dữ liệu thử của lần chạy trước không xóa được — xóa tay theo WARN rồi chạy lại.")

		print("== 1. Dữ liệu tạm ==")
		src = frappe.get_doc("POS Profile", pos_profile)
		if not src.get("branch"):
			raise RuntimeError(f"POS Profile {pos_profile} chưa có Branch.")
		wi = frappe.new_doc("Customer")
		wi.customer_name = f"{WALK_IN_PREFIX}{frappe.generate_hash(length=6)}"
		wi.customer_type = "Individual"
		wi.customer_group = frappe.db.get_single_value("Selling Settings", "customer_group") or "Individual"
		wi.territory = frappe.db.get_single_value("Selling Settings", "territory") or "All Territories"
		wi.insert(ignore_permissions=True)
		ctx["price_list"] = price_list or src.get("selling_price_list")
		modes = [p.mode_of_payment for p in (src.get("payments") or []) if p.mode_of_payment] or [mode_of_payment]
		for key, role in ROLE_OF.items():
			email = f"{PREFIX}.{key.lower()}@example.com"
			frappe.get_doc({"doctype": "User", "email": email, "first_name": f"ZZTEST {key}",
				"user_type": "System User", "send_welcome_email": 0, "enabled": 1,
				"roles": [{"role": role}]}).insert(ignore_permissions=True)
			users[key] = email

		def make_profile(members):
			prof = frappe.copy_doc(src)
			prof.set("__newname", f"{PROFILE_PREFIX}{frappe.generate_hash(length=6)}")
			prof.set("custom_walk_in_customer", wi.name)
			prof.disabled = 0
			prof.set("applicable_for_users", [])
			for key in members:
				prof.append("applicable_for_users", {"user": users[key], "default": 1})
			prof.flags.mypos_allow_shared_branch = True  # self-test: profile tạm cùng Branch với profile thật
			prof.insert(ignore_permissions=True)
			ctx["profiles"].append(prof.name)
			return prof.name

		prof1 = make_profile(("A", "M", "K"))
		prof2 = make_profile(("B",))

		def open_shift(profile, key):
			def _open():
				doc = frappe.get_doc({"doctype": "POS Opening Entry", "pos_profile": profile, "company": src.company,
					"user": users[key], "period_start_date": now_datetime(), "posting_date": nowdate(),
					"balance_details": [{"mode_of_payment": m, "opening_amount": 0} for m in modes]})
				doc.insert(ignore_permissions=True)
				doc.submit()
				return doc.name

			name, err = as_user(key, _open)
			if err:
				raise err
			return name

		card = frappe.get_doc({"doctype": "MYPOS Buzzer", "buzzer_number": f"{CARD_PREFIX}{frappe.generate_hash(length=4).upper()}",
			"branch": src.branch, "status": "Sẵn sàng"}).insert(ignore_permissions=True)
		frappe.db.commit()
		# Self-test: phiên bản tăng ngay (không chờ commit) để so trước / sau trong cùng giao dịch; mục 2 kiểm riêng "sau commit".
		frappe.flags.mypos_chg_immediate = True

		print("== 1b. Mở ca -> phiên bản của profile tăng (POS Opening Entry on_change) ==")
		shift1 = []
		changed("1b Mở ca profile 1 -> phiên bản profile 1 đổi", prof1, lambda: shift1.append(open_shift(prof1, "A")))
		open_shift(prof2, "B")
		print(f"INFO profile {prof1} (A, M, K) / {prof2} (B), ca {shift1}, thẻ {card.name}")

		print("== 2. Ghi sau commit: rollback không tăng, commit mới tăng ==")
		frappe.db.commit()
		frappe.flags.mypos_chg_immediate = False
		v0 = ver(prof1)
		CF.bump(prof1)
		ok("2a bump() chưa commit -> phiên bản CHƯA đổi", ver(prof1) == v0)
		frappe.db.rollback()
		ok("2b rollback -> phiên bản không đổi", ver(prof1) == v0)
		CF.bump(prof1)
		frappe.db.commit()
		ok("2c commit -> phiên bản đổi", ver(prof1) != v0, f"({v0} -> {ver(prof1)})")
		frappe.flags.mypos_chg_immediate = True

		print("== 3. get_pos_changes ==")
		res, err = as_user("A", P.get_pos_changes)
		ok("3a Cashier A: profile 1 + phiên bản = Redis", err is None and res and res["profile"] == prof1 and res["v"] == ver(prof1),
			f"({res}, {err})")
		res, err = as_user("K", P.get_pos_changes)
		ok("3b Kitchen K (thuộc profile 1): profile 1", err is None and res and res["profile"] == prof1, f"({res}, {err})")
		res, err = as_user("B", P.get_pos_changes)
		ok("3c Cashier B: profile 2", err is None and res and res["profile"] == prof2, f"({res}, {err})")
		q, _ms, _e = measure("get_pos_changes (đã cache)", "A", P.get_pos_changes)
		ok("3d get_pos_changes lần 2+ KHÔNG truy vấn đơn (≤ 1 SQL/lần)", q <= 1, f"({q} SQL/lần)")

		print("== 4. Phiên bản đổi ở mọi đường ghi; profile khác không đổi ==")
		v2 = ver(prof2)
		d = []
		changed("4a Tạo Draft (insert) -> đổi", prof1, lambda: d.append(draft("A", "Dine In", buzzer=card.name)))
		changed("4b pay_cash (submit) -> đổi", prof1, lambda: as_user("A", P.pay_cash, d[0]))
		changed("4c set_kitchen_status Đã làm (K) -> đổi", prof1, lambda: as_user("K", P.set_kitchen_status, d[0], "Đã làm"))
		changed("4d set_kitchen_status Đã hoàn thành (A) -> đổi", prof1, lambda: as_user("A", P.set_kitchen_status, d[0], "Đã hoàn thành"))
		dc = draft("A")
		changed("4e Hủy Draft (cancel_draft_order, set_value không chạy hook) -> đổi", prof1,
			lambda: as_user("A", P.cancel_draft_order, dc, 0, "Đặt nhầm"))
		ps = paid("A")

		def _cancel_submitted():
			inv = frappe.get_doc("POS Invoice", ps)
			inv.flags.ignore_permissions = True
			inv.cancel()

		changed("4f Hủy đơn đã thanh toán (on_cancel) -> đổi", prof1, _cancel_submitted)
		ok("4g Profile 2 không đổi khi profile 1 đổi", ver(prof2) == v2, f"({v2} -> {ver(prof2)})")
		v1 = ver(prof1)
		as_user("K", P.get_kitchen_orders)
		as_user("A", P.get_orders_shift, 200)
		as_user("A", P.get_pos_changes)
		ok("4h Chỉ đọc (get_kitchen_orders, get_orders_shift, get_pos_changes) -> không đổi", ver(prof1) == v1)
		key = frappe.cache.make_key(CF.COUNTER_PREFIX + prof1)
		frappe.cache.delete(key)
		ok("4i Mất khóa Redis (restart / xóa) -> phiên bản mới khác cũ (client tải lại, không sót)", ver(prof1) != v1,
			f"({v1} -> {ver(prof1)})")

		print("== 5. Pha chế chỉ đơn của profile user thuộc về (D1) ==")
		k1 = paid("A", "Dine In", buzzer=card.name)
		k2 = paid("B")
		rows, err = as_user("K", P.get_kitchen_orders)
		names = {o["name"] for o in rows or []}
		ok("5a Kitchen K thấy đơn profile 1, KHÔNG thấy đơn profile 2", err is None and k1 in names and k2 not in names,
			f"({err})")
		row = next((o for o in rows or [] if o["name"] == k1), {})
		ok("5b Số thẻ bàn đúng (gom 1 truy vấn)", row.get("buzzer_number") == card.buzzer_number, f"({row.get('buzzer_number')})")
		rows, err = as_user("M", P.get_kitchen_orders)
		ok("5c Manager M (profile 1) thấy đơn profile 1, không thấy profile 2",
			err is None and k1 in {o["name"] for o in rows or []} and k2 not in {o["name"] for o in rows or []}, f"({err})")
		_r, err = as_user("K2", P.get_kitchen_orders)
		blocked("5d Kitchen K2 không thuộc profile nào: get_kitchen_orders báo rõ", err, "chưa thuộc POS Profile", "Applicable for Users")
		_r, err = as_user("K2", P.get_pos_config)
		blocked("5e Kitchen K2: get_pos_config báo rõ (cùng thông báo)", err, "chưa thuộc POS Profile")

		print("== 6. get_orders_shift = get_orders(draft) + get_orders(paid) + get_orders_summary(shift) ==")
		draft("A")
		bundle, err = as_user("A", P.get_orders_shift, 200)
		dr = as_user("A", P.get_orders, "draft", 200)[0] or []
		pd = as_user("A", P.get_orders, "paid", 200)[0] or []
		sm = as_user("A", P.get_orders_summary, "shift")[0] or {}
		ok("6a Cùng danh sách + bộ đếm", err is None and bundle
			and [o["name"] for o in bundle["drafts"]] == [o["name"] for o in dr]
			and [o["name"] for o in bundle["paid"]] == [o["name"] for o in pd]
			and bundle["summary"]["counts"] == sm.get("counts"), f"({err})")
		prow = next((o for o in bundle["paid"] if o["name"] == k1), {}) if bundle else {}
		ok("6b Số thẻ bàn trong Orders đúng (gom 1 truy vấn)", prow.get("buzzer_number") == card.buzzer_number,
			f"({prow.get('buzzer_number')})")

		print("== 7. Cache POS Profile của user: lưu POS Profile -> xóa cache ==")
		as_user("A", P.get_pos_changes)  # cache profile 1 cho A
		p2 = frappe.get_doc("POS Profile", prof2)
		p2.append("applicable_for_users", {"user": users["K2"], "default": 1})
		p2.flags.mypos_allow_shared_branch = True
		p2.save(ignore_permissions=True)
		frappe.db.commit()
		res, err = as_user("K2", P.get_pos_changes)
		ok("7a K2 vừa được thêm vào profile 2 -> get_pos_changes trả profile 2 ngay", err is None and res and res["profile"] == prof2,
			f"({res}, {err})")
		rows, err = as_user("K2", P.get_kitchen_orders)
		ok("7b K2 thấy đơn profile 2", err is None and k2 in {o["name"] for o in rows or []}, f"({err})")

		print(f"== 8. Đo ({rounds} lần / API; so với số liệu trước khi sửa) ==")
		measure("get_pos_changes", "A", P.get_pos_changes)
		measure("get_kitchen_orders (K)", "K", P.get_kitchen_orders)
		measure("get_orders_shift", "A", P.get_orders_shift, 200)
		measure("get_orders x2 + summary (cũ)", "A", lambda: (P.get_orders("draft", 200), P.get_orders("paid", 200),
			P.get_orders_summary("shift")))
		measure("get_serve_queue", "A", P.get_serve_queue)
		measure("get_buzzers", "A", P.get_buzzers)
		measure("get_order_detail", "A", P.get_order_detail, k1)
		print("INFO EXPLAIN truy vấn Pha chế:")
		for r in frappe.db.sql(
			"EXPLAIN SELECT name FROM `tabPOS Invoice` WHERE docstatus = 1 AND status = 'Paid' AND pos_profile = %s "
			"AND custom_kitchen_status IN ('Chưa làm', 'Đã làm') ORDER BY creation", (prof1,), as_dict=True):
			print(f"     table={r.get('table')} type={r.get('type')} key={r.get('key')} rows={r.get('rows')} extra={r.get('Extra')}")
	except Exception:
		ok("Lỗi ngoài dự kiến", False)
		traceback.print_exc()
	finally:
		frappe.flags.mypos_chg_immediate = False
		try:
			frappe.set_user("Administrator")
			frappe.db.rollback()
			removed, failed = purge_leftovers()
			report_cleanup(removed, failed, "cuối")
			frappe.db.commit()
			left = frappe.get_all("POS Profile", filters={"name": ["like", PROFILE_PREFIX + "%"]}, pluck="name") \
				+ frappe.get_all("User", filters={"name": ["like", PREFIX + ".%"]}, pluck="name") \
				+ frappe.get_all("Customer", filters={"customer_name": ["like", WALK_IN_PREFIX + "%"]}, pluck="name") \
				+ frappe.get_all("MYPOS Buzzer", filters={"buzzer_number": ["like", CARD_PREFIX + "%"]}, pluck="name") \
				+ frappe.get_all("POS Invoice", filters={"pos_profile": ["in", ctx["profiles"] or [""]]}, pluck="name")
			ok("9 Dọn dữ liệu: không còn profile / user / thẻ / đơn thử trong DB", not left, f"({left})")
		except Exception:  # noqa: BLE001
			ok("9 Dọn dữ liệu (lỗi khi dọn — xem WARN / traceback)", False)
			traceback.print_exc()
		finally:
			try:
				frappe.set_user(admin)
			except Exception:  # noqa: BLE001
				pass

	failed_cases = [c for c, ok_ in results if not ok_]
	print("== KẾT QUẢ:", "PASS" if not failed_cases else f"FAIL ({len(failed_cases)})",
		f"— {len(results) - len(failed_cases)}/{len(results)} ==")
	return not failed_cases
