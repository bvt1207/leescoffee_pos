def check_walk_in_customer(pos_profile=None, item_code=None, mode_of_payment=None, price_list=None):
	"""Khách vãng lai theo POS Profile (2026-11-24): field POS Profile.custom_walk_in_customer, không còn tên Customer cố định.

	Dán CẢ hàm vào `bench --site <site> console` MỚI (SAU khi migrate) rồi gọi, ví dụ:
	    check_walk_in_customer("POS TEST", "<mã món VARIANT>", "Cash", price_list="<Price List của MYPOS Menu>")

	KHÔNG đụng ca / đơn / khách thật: chép POS Profile thành 3 profile "ZZTEST WalkIn ..." (P1: khách vãng lai 1, user A;
	P2: khách vãng lai 2, user B; P0: chưa cấu hình, user C), user tạm A, B, C (POS CASHIER), K (POS KITCHEN),
	Customer tạm "ZZTEST WI <tag> ...". Ca do create_draft_order tự mở. Không đóng ca (đóng ca + gộp đơn: kiểm tay).
	Cuối hàm dọn mọi dữ liệu thử: commit trước mỗi lần xóa, thử lại 3 lần khi QueryDeadlockError, Contact trước User;
	lỗi dọn chỉ in WARN + lệnh xóa tay; dòng KẾT QUẢ luôn được in.
	Sau khi PASS: chạy lại check_table_card(...), run_order_qr_selftest(), run_order_history_selftest() (luồng QR không đổi).
	"""
	if pos_profile is None:  # không truyền dữ liệu -> tự dựng quán thử tạm (selfcheck/test_shop.py), dọn ở cuối
		from mypos.selfcheck.test_shop import zz_test_shop

		_shop = zz_test_shop("create", open_shift=False)
		if not _shop.get("ok"):
			print(f"SKIP: {_shop.get('reason')}")
			print("KẾT QUẢ: SKIP")
			return None
		try:
			return check_walk_in_customer(_shop["pos_profile"], _shop["item"], _shop["mop_cash"], _shop["price_list"])
		finally:
			zz_test_shop("drop", _shop["tag"])

	import time
	import traceback

	import frappe

	from mypos.mypos.api import customer_order_api as Q
	from mypos.mypos.api import pos_api as P
	from mypos.mypos.doctype.pos_invoice_hooks.pos_invoice_hooks import get_status_board_orders
	from mypos.mypos.doctype.pos_profile_hooks.pos_profile_hooks import WALK_IN_MISSING_MSG

	PREFIX = "zz.test.walkin"
	PROFILE_PREFIX = "ZZTEST WalkIn "
	CUST_PREFIX = "ZZTEST WI "
	FIELD = "custom_walk_in_customer"
	ROLE_OF = {"A": "POS CASHIER", "B": "POS CASHIER", "C": "POS CASHIER", "K": "POS KITCHEN"}
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
			for c in frappe.get_all("Customer", filters={"customer_name": ["like", CUST_PREFIX + "%"]}, pluck="name"):
				for n in frappe.get_all("POS Invoice", filters={"customer": c}, pluck="name"):
					delete_fresh("POS Invoice", n, removed, failed, cancel=True)
				delete_fresh("Customer", c, removed, failed)
			contacts = set(frappe.get_all("Contact", filters={"user": ["like", PREFIX + ".%"]}, pluck="name"))
			contacts |= set(frappe.get_all("Contact", filters={"email_id": ["like", PREFIX + ".%"]}, pluck="name"))
			for c in sorted(contacts):
				delete_fresh("Contact", c, removed, failed)
			for u in frappe.get_all("User", filters={"name": ["like", PREFIX + ".%"]}, pluck="name"):
				frappe.clear_cache(user=u)
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
	def line(qty=1):
		return [{"item_code": item_code, "qty": qty, "options": []}]

	def draft(key, customer=None, order_type="Take Away"):
		res, err = as_user(key, P.create_draft_order, line(), order_type, customer_name=customer,
			mode_of_payment=mode_of_payment, price_list=ctx["price_list"])
		if err:
			raise err
		return res["invoice_name"]

	def paid(key, customer=None):
		name = draft(key, customer)
		_r, err = as_user(key, P.pay_cash, name)
		if err:
			raise err
		return name

	def make_customer(label, mobile=None, disabled=0, loyalty_program=None):
		doc = frappe.new_doc("Customer")
		doc.customer_name = f"{CUST_PREFIX}{ctx['tag']} {label}"
		doc.customer_type = "Individual"
		doc.customer_group = frappe.db.get_single_value("Selling Settings", "customer_group") or "Individual"
		doc.territory = frappe.db.get_single_value("Selling Settings", "territory") or "All Territories"
		if mobile:
			doc.mobile_number = mobile
		doc.disabled = disabled
		if loyalty_program:
			doc.loyalty_program = loyalty_program
		doc.insert(ignore_permissions=True)
		return doc.name

	def save_walk_in(profile, customer):
		"""Lưu POS Profile với khách vãng lai `customer`; trả lỗi (None = lưu được). Lỗi -> rollback, profile giữ nguyên."""
		try:
			doc = frappe.get_doc("POS Profile", profile)
			doc.set(FIELD, customer)
			# Profile tạm cùng Branch với quán thử / profile khác (quy tắc 1 profile đang bật / Branch, 2026-11-25) -> cờ self-test.
			doc.flags.mypos_allow_shared_branch = True
			doc.save(ignore_permissions=True)
			frappe.db.commit()
			return None
		except Exception as e:  # noqa: BLE001
			frappe.db.rollback()
			frappe.clear_messages()
			return e

	admin = frappe.session.user
	frappe.set_user("Administrator")
	try:
		print("== 0. Dọn dữ liệu thử còn sót ==")
		removed0, failed0 = purge_leftovers()
		report_cleanup(removed0, failed0, "đầu")
		if failed0:
			raise RuntimeError("Còn dữ liệu thử của lần chạy trước không xóa được — xóa tay theo WARN rồi chạy lại.")

		print("== 1. Dữ liệu tạm ==")
		if not frappe.db.has_column("POS Profile", FIELD):
			raise RuntimeError(f"POS Profile chưa có cột {FIELD} — chạy bench migrate trước.")
		src = frappe.get_doc("POS Profile", pos_profile)
		ctx["price_list"] = price_list or src.get("selling_price_list")
		ctx["tag"] = frappe.generate_hash(length=4).upper()
		for key, role in ROLE_OF.items():
			email = f"{PREFIX}.{key.lower()}@example.com"
			frappe.get_doc({"doctype": "User", "email": email, "first_name": f"ZZTEST {key}",
				"user_type": "System User", "send_welcome_email": 0, "enabled": 1,
				"roles": [{"role": role}]}).insert(ignore_permissions=True)
			users[key] = email

		rnd = frappe.generate_hash(length=8)
		digits = "".join(str(int(ch, 16) % 10) for ch in rnd)[:7]
		real_mobile, phone_mobile = f"097{digits}", f"096{digits}"
		w1 = make_customer("Vang lai 1")
		w2 = make_customer("Vang lai 2")
		real = make_customer("Khach that", mobile=real_mobile)
		off = make_customer("Disabled", disabled=1)
		phone = make_customer("Co SDT", mobile=phone_mobile)

		def make_profile(members, walk_in):
			prof = frappe.copy_doc(src)
			prof.set("__newname", f"{PROFILE_PREFIX}{frappe.generate_hash(length=6)}")
			prof.disabled = 0
			prof.set(FIELD, walk_in)
			prof.set("applicable_for_users", [])
			for key in members:
				prof.append("applicable_for_users", {"user": users[key], "default": 1})
			# 2026-11-25: mỗi Branch tối đa 1 profile đang bật (pos_profile_hooks). Profile tạm cùng Branch với profile thật
			# -> bật cờ chỉ dùng cho self-test (không đặt được từ Desk/API).
			prof.flags.mypos_allow_shared_branch = True
			prof.insert(ignore_permissions=True)
			ctx["profiles"].append(prof.name)
			return prof.name

		# K (POS KITCHEN) thuộc P1: từ 2026-11-25 (quy tắc D1, rules/realtime.md §4) Pha chế chỉ thấy đơn của profile mình thuộc về.
		p1 = make_profile(("A", "K"), w1)
		p2 = make_profile(("B",), w2)
		p0 = make_profile(("C",), None)
		frappe.db.commit()
		print(f"INFO P1 {p1} ({w1}) / P2 {p2} ({w2}) / P0 {p0} (chưa cấu hình); khách thật {real}")

		print("== 2. Profile chưa cấu hình -> chặn đơn không chọn khách ==")
		_r, err = as_user("C", P.create_draft_order, line(), "Take Away", mode_of_payment=mode_of_payment,
			price_list=ctx["price_list"])
		blocked("2a create_draft_order không chọn khách bị chặn đúng thông báo", err, WALK_IN_MISSING_MSG)
		ok("2b Không có đơn nào được tạo ở P0", not frappe.db.exists("POS Invoice", {"pos_profile": p0}))
		_r, err = as_user("C", P.preview_pricing, line(), price_list=ctx["price_list"])
		blocked("2c preview_pricing không chọn khách bị chặn đúng thông báo", err, WALK_IN_MISSING_MSG)
		cfg, err = as_user("C", P.get_pos_config)
		ok("2d get_pos_config: walk_in_configured = False + có cảnh báo",
			err is None and cfg["profile"]["walk_in_configured"] is False and WALK_IN_MISSING_MSG in cfg["warnings"],
			f"({err or cfg['profile']})")
		d0, err = as_user("C", P.create_draft_order, line(), "Take Away", customer_name=real,
			mode_of_payment=mode_of_payment, price_list=ctx["price_list"])
		ok("2e Chọn khách thật vẫn tạo đơn được ở P0", err is None and d0, f"({err})")

		print("== 3. Mỗi profile dùng khách vãng lai của mình ==")
		a1 = paid("A")
		b1 = paid("B")
		ok("3a Đơn P1 không chọn khách -> khách vãng lai P1", frappe.db.get_value("POS Invoice", a1, "customer") == w1)
		ok("3b Đơn P2 không chọn khách -> khách vãng lai P2", frappe.db.get_value("POS Invoice", b1, "customer") == w2)
		cfg, _e = as_user("A", P.get_pos_config)
		ok("3c get_pos_config P1: walk_in_customer đúng, configured", cfg and cfg["profile"]["walk_in_customer"] == w1
			and cfg["profile"]["walk_in_configured"] is True)

		print("== 4. Cờ is_walk_in ==")
		r1 = paid("A", real)
		orders, err = as_user("A", P.get_orders)
		by = {o["name"]: o for o in orders or []}
		ok("4a get_orders: khách vãng lai True, khách thật False",
			by.get(a1, {}).get("is_walk_in") is True and by.get(r1, {}).get("is_walk_in") is False, f"({err})")
		det_a, _e = as_user("A", P.get_order_detail, a1)
		det_r, _e2 = as_user("A", P.get_order_detail, r1)
		ok("4b get_order_detail: True / False", det_a and det_a["is_walk_in"] is True and det_r and det_r["is_walk_in"] is False)
		kit, err = as_user("K", P.get_kitchen_orders, "Chưa làm")
		kby = {o["name"]: o for o in kit or []}
		ok("4c get_kitchen_orders (K thuộc P1): khách vãng lai P1 True, khách thật False; đơn P2 KHÔNG hiện (D1)",
			kby.get(a1, {}).get("is_walk_in") is True and kby.get(r1, {}).get("is_walk_in") is False and b1 not in kby,
			f"({err or sorted(kby)})")
		real_name = frappe.db.get_value("Customer", real, "customer_name")
		ok("4c2 get_kitchen_orders: customer_name có cho khách vãng lai và khách thật (đúng tên khách thật)",
			bool(kby.get(a1, {}).get("customer_name")) and kby.get(r1, {}).get("customer_name") == real_name,
			f"({kby.get(a1, {}).get('customer_name')} / {kby.get(r1, {}).get('customer_name')})")
		# KITCHEN chỉ nhận thêm tên khách + is_walk_in: không SĐT, điểm, tiền, thanh toán (2026-11-24, màn Pha chế).
		SENSITIVE = {"mobile_number", "mobile_no", "contact_mobile", "phone", "loyalty_points", "loyalty_program",
			"redeemed_points", "payment_code", "payment_status", "transaction_ref", "sepay_payment_log",
			"grand_total", "rounded_total", "amount", "rate", "price_list_rate", "customer_mobile"}
		leaked = sorted({k for o in kit or [] for k in o if k in SENSITIVE}
			| {k for o in kit or [] for it in o.get("items", []) for k in it if k in SENSITIVE})
		phone_hit = [o["name"] for o in kit or [] if real_mobile in str(o)]
		ok("4g get_kitchen_orders (KITCHEN): không có khóa nhạy cảm, không chứa SĐT khách thật",
			not leaked and not phone_hit, f"(khóa {leaked}, đơn chứa SĐT {phone_hit})")
		board = {o["invoice_name"]: o for o in get_status_board_orders()}
		ok("4d get_status_board_orders: True / False",
			board.get(a1, {}).get("is_walk_in") is True and board.get(r1, {}).get("is_walk_in") is False)
		# Chéo: khách vãng lai của P2 đặt ở P1 (chọn như khách thường) -> không phải khách vãng lai của P1.
		x1 = paid("A", w2)
		det_x, _e = as_user("A", P.get_order_detail, x1)
		ok("4e Khách vãng lai của P2 trên đơn P1 -> is_walk_in False (tính theo profile của đơn)",
			det_x and det_x["is_walk_in"] is False)
		for n in (a1, r1):
			_r, err = as_user("K", P.set_kitchen_status, n, "Đã làm")
			if err:
				raise err
		q, err = as_user("A", P.get_serve_queue)
		qby = {o["name"]: o for o in q or []}
		ok("4f get_serve_queue: khách vãng lai -> customer_name '' + is_walk_in True; khách thật có tên",
			qby.get(a1, {}).get("customer_name") == "" and qby.get(a1, {}).get("is_walk_in") is True
			and qby.get(r1, {}).get("customer_name") and qby.get(r1, {}).get("is_walk_in") is False, f"({err})")

		print("== 5. Loyalty / tìm khách ==")
		lo, err = as_user("A", P.get_customer_loyalty, w1)
		ok("5a get_customer_loyalty(khách vãng lai) -> enrolled False", err is None and lo == {"enrolled": False}, f"({err or lo})")
		_r, err = as_user("A", P.create_draft_order, line(), "Take Away", mode_of_payment=mode_of_payment,
			price_list=ctx["price_list"], redeem_points=1)
		blocked("5b Đổi điểm cho khách vãng lai bị chặn", err, "tích điểm")
		found, err = as_user("A", P.search_customers, f"{CUST_PREFIX}{ctx['tag']}", 20)
		names = {r["name"] for r in found or []}
		ok("5c search_customers: có khách thật, KHÔNG có khách vãng lai P1/P2",
			real in names and w1 not in names and w2 not in names, f"({err or sorted(names)})")
		lpe = frappe.db.count("Loyalty Point Entry", {"invoice_type": "POS Invoice", "invoice": ["in", [a1, b1]]})
		ok("5d Đơn khách vãng lai đã thanh toán: Customer chưa có Loyalty Program, không có Loyalty Point Entry",
			not frappe.db.get_value("Customer", w1, "loyalty_program")
			and not frappe.db.get_value("Customer", w2, "loyalty_program") and lpe == 0, f"(LPE={lpe})")

		print("== 6. Lưu POS Profile ==")
		frappe.db.commit()  # save_walk_in rollback khi bị chặn: không được cuốn mất đơn của các bước trên
		err = save_walk_in(p1, f"{CUST_PREFIX}KHONG-CO-{ctx['tag']}")
		ok("6a Customer không tồn tại -> không lưu được", err is not None, f"-> {type(err).__name__}: {str(err)[:120]}")
		err = save_walk_in(p1, off)
		blocked("6b Customer disabled -> chặn", err, "vô hiệu hóa")
		lp = frappe.db.get_value("Loyalty Program", {}, "name")
		if lp:
			lp_cust = make_customer("Co diem", loyalty_program=lp)
			frappe.db.commit()
			err = save_walk_in(p1, lp_cust)
			blocked("6c Customer có Loyalty Program -> chặn", err, "tích điểm")
		else:
			print("SKIP 6c: site không có Loyalty Program nào")
		ok("6d Sau các lần bị chặn, P1 vẫn giữ khách vãng lai cũ", frappe.db.get_value("POS Profile", p1, FIELD) == w1)
		err = save_walk_in(p1, phone)
		ok("6e Customer có SĐT -> vẫn lưu được (chỉ cảnh báo)", err is None and frappe.db.get_value("POS Profile", p1, FIELD) == phone,
			f"({err})")

		print("== 7. Web đặt món QR: không đăng nhập vào khách vãng lai ==")
		try:
			Q._find_customer(phone_mobile)
			ok("7a SĐT của khách vãng lai -> chặn đăng nhập QR", False, "-> KHÔNG bị chặn")
		except Exception as e:  # noqa: BLE001
			frappe.clear_messages()
			blocked("7a SĐT của khách vãng lai -> chặn đăng nhập QR", e, "không dùng được")
		ok("7b SĐT khách thật -> đúng Customer", Q._find_customer(real_mobile) == real)
		err = save_walk_in(p1, w1)
		ok("7c Trả P1 về khách vãng lai 1; SĐT cũ của khách vãng lai đăng nhập lại được (là khách thường)",
			err is None and Q._find_customer(phone_mobile) == phone, f"({err})")
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
				+ frappe.get_all("Customer", filters={"customer_name": ["like", CUST_PREFIX + "%"]}, pluck="name") \
				+ frappe.get_all("POS Invoice", filters={"pos_profile": ["in", ctx["profiles"] or [""]]}, pluck="name")
			ok("8 Dọn dữ liệu: không còn profile / user / khách / đơn thử trong DB", not left, f"({left})")
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
