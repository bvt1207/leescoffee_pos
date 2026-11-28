def check_customer_display(pos_profile=None, item_code=None, mode_of_payment=None, price_list=None):
	"""Màn hình khách /pos/customer (2026-11-24): MYPOS Banner + customer_display_api.

	Dán CẢ hàm vào `bench --site <site> console` MỚI (SAU khi migrate) rồi gọi, ví dụ:
	    check_customer_display("POS TEST", "<mã món VARIANT>", "Cash", price_list="<Price List của MYPOS Menu>")

	KHÔNG đụng ca / đơn / banner thật: chép POS Profile thành 2 profile "ZZTEST CD ..." (A ở profile 1, B ở profile 2),
	user tạm A, B (POS CASHIER), K (POS KITCHEN), Customer khách vãng lai tạm "ZZTEST WI CD ...", banner tạm "ZZTEST BNR ...".
	Trạng thái màn khách nằm ở Redis cache (`mypos_cdisplay:<user>`); điểm móc từ đơn hàng ghi SAU commit nên script
	commit trước khi đọc. Cuối hàm dọn mọi dữ liệu thử + khóa cache; dòng KẾT QUẢ luôn được in.
	"""
	if pos_profile is None:  # không truyền dữ liệu -> tự dựng quán thử tạm (selfcheck/test_shop.py), dọn ở cuối
		from mypos.selfcheck.test_shop import zz_test_shop

		_shop = zz_test_shop("create", open_shift=False)
		if not _shop.get("ok"):
			print(f"SKIP: {_shop.get('reason')}")
			print("KẾT QUẢ: SKIP")
			return None
		try:
			return check_customer_display(_shop["pos_profile"], _shop["item"], _shop["mop_cash"], _shop["price_list"])
		finally:
			zz_test_shop("drop", _shop["tag"])

	import time
	import traceback

	import frappe
	from frappe.utils import add_days, now_datetime, nowdate

	from mypos.mypos.api import customer_display_api as D
	from mypos.mypos.api import pos_api as P

	PREFIX = "zz.test.cd"
	PROFILE_PREFIX = "ZZTEST CD "
	WALK_IN_PREFIX = "ZZTEST WI CD "
	BANNER_PREFIX = "ZZTEST BNR "
	ROLE_OF = {"A": "POS CASHIER", "B": "POS CASHIER", "K": "POS KITCHEN"}
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
			f"-> {type(err).__name__}: {str(err)[:140]}" if err else "-> KHÔNG bị chặn")

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
				for n in frappe.get_all("MYPOS Banner", filters={"pos_profile": prof}, pluck="name"):
					delete_fresh("MYPOS Banner", n, removed, failed)
				delete_fresh("POS Profile", prof, removed, failed)
			for n in frappe.get_all("MYPOS Banner", filters={"title": ["like", BANNER_PREFIX + "%"]}, pluck="name"):
				delete_fresh("MYPOS Banner", n, removed, failed)
			for c in frappe.get_all("Customer", filters={"customer_name": ["like", WALK_IN_PREFIX + "%"]}, pluck="name"):
				for n in frappe.get_all("POS Invoice", filters={"customer": c}, pluck="name"):
					delete_fresh("POS Invoice", n, removed, failed, cancel=True)
				delete_fresh("Customer", c, removed, failed)
			contacts = set(frappe.get_all("Contact", filters={"user": ["like", PREFIX + ".%"]}, pluck="name"))
			contacts |= set(frappe.get_all("Contact", filters={"email_id": ["like", PREFIX + ".%"]}, pluck="name"))
			for c in sorted(contacts):
				delete_fresh("Contact", c, removed, failed)
			for u in frappe.get_all("User", filters={"name": ["like", PREFIX + ".%"]}, pluck="name"):
				frappe.cache.delete_value(D._key(u))
				frappe.clear_cache(user=u)
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
	LINE = [{"item_code": item_code, "qty": 2, "options": []}]

	def state(key, since=0):
		res, err = as_user(key, D.get_customer_display_state, since)
		if err:
			raise err
		return res

	def draft(key="A"):
		res, err = as_user(key, P.create_draft_order, LINE, "Take Away", mode_of_payment=mode_of_payment,
			price_list=ctx["price_list"])
		if err:
			raise err
		frappe.db.commit()  # điểm móc màn khách ghi sau commit
		return res["invoice_name"]

	def banner(title, image, **kw):
		doc = frappe.get_doc({"doctype": "MYPOS Banner", "title": BANNER_PREFIX + title, "image": image, **kw})
		doc.insert(ignore_permissions=True)
		return doc.name

	admin = frappe.session.user
	frappe.set_user("Administrator")
	try:
		print("== 0. Dọn dữ liệu thử còn sót ==")
		removed0, failed0 = purge_leftovers()
		report_cleanup(removed0, failed0, "đầu")
		if failed0:
			raise RuntimeError("Còn dữ liệu thử của lần chạy trước không xóa được — xóa tay theo WARN rồi chạy lại.")

		print("== 1. Dữ liệu tạm ==")
		item = frappe.db.get_value("Item", item_code, ["has_variants", "variant_of"], as_dict=True)
		if not item:
			raise RuntimeError(f"Không có Item {item_code}.")
		if item.has_variants and not item.variant_of:
			variants = frappe.get_all("Item", filters={"variant_of": item_code, "disabled": 0}, pluck="name", limit=10)
			raise RuntimeError(
				f"{item_code} là món template (có size) — truyền mã VARIANT có giá trong Price List, vd. {variants}."
			)
		src = frappe.get_doc("POS Profile", pos_profile)
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
			# 2026-11-25: mỗi Branch tối đa 1 profile đang bật (pos_profile_hooks). Profile tạm cùng Branch với profile thật
			# -> bật cờ chỉ dùng cho self-test (không đặt được từ Desk/API).
			prof.flags.mypos_allow_shared_branch = True
			prof.insert(ignore_permissions=True)
			ctx["profiles"].append(prof.name)
			return prof.name

		prof1 = make_profile(("A", "K"))
		prof2 = make_profile(("B",))

		def open_shift():
			doc = frappe.get_doc({"doctype": "POS Opening Entry", "pos_profile": prof1, "company": src.company,
				"user": users["A"], "period_start_date": now_datetime(), "posting_date": nowdate(),
				"balance_details": [{"mode_of_payment": m, "opening_amount": 0} for m in modes]})
			doc.insert(ignore_permissions=True)
			doc.submit()
			return doc.name

		shift, err = as_user("A", open_shift)
		if err:
			raise err
		frappe.db.commit()
		print(f"INFO profile {prof1} (A, K) / {prof2} (B), ca {shift}")

		print("== 2. MYPOS Banner: lọc theo POS Profile, hiệu lực, đang dùng, thứ tự ==")
		img = "/files/zztest-banner.jpg"
		today = nowdate()
		b_all = banner("Mọi profile", img, sort_order=2)
		b_p1 = banner("Profile 1", img, pos_profile=prof1, sort_order=1)
		banner("Profile 2", img, pos_profile=prof2, sort_order=0)
		banner("Tắt", img, enabled=0)
		banner("Hết hạn", img, valid_upto=add_days(today, -1))
		banner("Chưa tới", img, valid_from=add_days(today, 1))
		frappe.db.commit()
		cfg, err = as_user("A", D.get_customer_display_config)
		mine = [b["title"] for b in (cfg or {}).get("banners", []) if b["title"].startswith(BANNER_PREFIX)]
		ok("2a Cashier A (profile 1): chỉ thấy 'Profile 1' rồi 'Mọi profile' (theo Thứ tự)",
			err is None and mine == [BANNER_PREFIX + "Profile 1", BANNER_PREFIX + "Mọi profile"], f"({err or mine})")
		cfg_b, err = as_user("B", D.get_customer_display_config)
		mine_b = [b["title"] for b in (cfg_b or {}).get("banners", []) if b["title"].startswith(BANNER_PREFIX)]
		ok("2b Cashier B (profile 2): 'Profile 2' rồi 'Mọi profile', không thấy banner profile 1",
			err is None and mine_b == [BANNER_PREFIX + "Profile 2", BANNER_PREFIX + "Mọi profile"], f"({err or mine_b})")
		ok("2c Cấu hình không lộ SePay / tài khoản", cfg and not any(k in str(cfg).lower() for k in ("api_key", "secret", "va_account", "income_account")))
		try:
			banner("Sai ngày", img, valid_from=today, valid_upto=add_days(today, -1))
			ok("2d Hiệu lực từ > Hiệu lực đến -> chặn lưu", False, "-> KHÔNG bị chặn")
		except Exception as e:  # noqa: BLE001
			frappe.clear_messages()
			ok("2d Hiệu lực từ > Hiệu lực đến -> chặn lưu", "hiệu lực" in str(e).lower(), f"-> {str(e)[:120]}")
		print(f"INFO banner {b_all}, {b_p1}")

		print("== 3. KITCHEN bị chặn ==")
		for fn, args in ((D.get_customer_display_config, ()), (D.get_customer_display_state, (0,)),
				(D.set_customer_display, ("idle",))):
			_r, err = as_user("K", fn, *args)
			blocked(f"3 KITCHEN gọi {fn.__name__} -> chặn", err, "không có quyền")

		print("== 4. Giỏ: preview_pricing(display=1) -> màn khách hiện đúng số tiền server tính ==")
		s0 = state("A")
		res0, err = as_user("A", P.preview_pricing, LINE, price_list=ctx["price_list"])
		ok("4a preview không display -> trạng thái không đổi", err is None and state("A").get("v") == s0.get("v"), f"({err})")
		res, err = as_user("A", P.preview_pricing, LINE, price_list=ctx["price_list"], display=1)
		s4 = state("A")
		t = (s4.get("order") or {}).get("totals") or {}
		ok("4b phase cart, Tổng/phụ thu/KM khớp preview, 1 dòng qty 2",
			err is None and s4.get("phase") == "cart" and abs(t.get("grand_total", -1) - res["grand_total"]) < 0.01
			and abs(t.get("total_surcharge", -1) - res["total_surcharge"]) < 0.01
			and abs(t.get("total_discount_rules", -1) - res["total_discount_rules"]) < 0.01
			and len(s4["order"]["lines"]) == 1 and s4["order"]["lines"][0]["qty"] == 2, f"({err or t})")
		cust4 = (s4.get("order") or {}).get("customer") or {}
		ok("4c Khách vãng lai -> is_walk_in, không lộ tên Customer",
			cust4.get("is_walk_in") is True and cust4.get("name") == "", f"({cust4})")
		ok("4d Gọi lại với since = v -> unchanged", state("A", s4["v"]).get("unchanged") is True)
		_r, err = as_user("A", D.set_customer_display, "idle")
		ok("4e Giỏ rỗng (idle) khi đang hiện giỏ -> idle", err is None and state("A").get("phase") == "idle", f"({err})")

		print("== 5. Tạo đơn -> order; giỏ rỗng không xóa đơn; tiền mặt -> paid, phải thu 0 ==")
		d5 = draft()
		s5 = state("A")
		inv5 = frappe.db.get_value("POS Invoice", d5, ["rounded_total", "grand_total"], as_dict=True)
		due5 = inv5.rounded_total or inv5.grand_total
		ok("5a create_draft_order -> phase order, đúng đơn, phải thu = tổng đơn",
			s5.get("phase") == "order" and s5["order"]["invoice"] == d5
			and abs(s5["order"]["totals"]["amount_due"] - due5) < 0.01, f"({s5.get('phase')}, {due5})")
		as_user("A", D.set_customer_display, "idle")
		ok("5b set idle sau khi tạo đơn -> vẫn hiện đơn (phase order)", state("A").get("phase") == "order")
		_r, err = as_user("A", P.pay_cash, d5)
		frappe.db.commit()
		s5c = state("A")
		ok("5c pay_cash -> phase paid, phải thu 0, paid_at có",
			err is None and s5c.get("phase") == "paid" and s5c["order"]["totals"]["amount_due"] == 0 and s5c.get("paid_at"),
			f"({err or s5c.get('phase')})")

		print("== 6. Cô lập theo user / POS Profile ==")
		d6 = draft()
		s_b = state("B")
		ok("6a Cashier B không thấy đơn của A", d6 not in str(s_b), f"({s_b.get('phase')})")
		_r, err = as_user("B", D.set_customer_display, "order", d6)
		blocked("6b B đặt màn khách hiện đơn của profile 1 -> chặn", err, "không hiển thị được")
		_r, err = as_user("A", D.set_customer_display, "order", d5)
		blocked("6c Đặt hiện đơn đã thanh toán -> chặn", err, "không hiển thị được")
		_r, err = as_user("A", D.set_customer_display, "order", d6)
		ok("6d A chọn đơn Draft của mình -> order", err is None and state("A").get("order", {}).get("invoice") == d6, f"({err})")

		print("== 7. Hủy đơn đang hiện -> idle ==")
		_r, err = as_user("A", P.cancel_draft_order, d6, 0, "Khách đổi ý")
		frappe.db.commit()
		ok("7a cancel_draft_order -> màn khách về idle", err is None and state("A").get("phase") == "idle", f"({err})")
	except Exception:
		ok("Lỗi ngoài dự kiến", False)
		traceback.print_exc()
	finally:
		try:
			frappe.set_user("Administrator")
			frappe.db.rollback()
			removed, failed = purge_leftovers()
			report_cleanup(removed, failed, "cuối")
			frappe.db.commit()
			left = frappe.get_all("POS Profile", filters={"name": ["like", PROFILE_PREFIX + "%"]}, pluck="name") \
				+ frappe.get_all("User", filters={"name": ["like", PREFIX + ".%"]}, pluck="name") \
				+ frappe.get_all("Customer", filters={"customer_name": ["like", WALK_IN_PREFIX + "%"]}, pluck="name") \
				+ frappe.get_all("MYPOS Banner", filters={"title": ["like", BANNER_PREFIX + "%"]}, pluck="name") \
				+ frappe.get_all("POS Invoice", filters={"pos_profile": ["in", ctx["profiles"] or [""]]}, pluck="name")
			ok("8 Dọn dữ liệu: không còn profile / user / banner / đơn thử trong DB", not left, f"({left})")
		except Exception:  # noqa: BLE001
			ok("8 Dọn dữ liệu (lỗi khi dọn — xem WARN / traceback)", False)
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
