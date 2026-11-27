def check_table_card(pos_profile=None, item_code=None, mode_of_payment=None, price_list=None):
	"""Thẻ bàn (đổi từ thẻ rung, 2026-11-23) + hàng chờ phục vụ của thu ngân (pos_api.get_serve_queue).

	Dán CẢ hàm vào `bench --site <site> console` MỚI (SAU khi migrate) rồi gọi, ví dụ:
	    check_table_card("POS TEST", "<mã món VARIANT>", "Cash", price_list="<Price List của MYPOS Menu>")

	KHÔNG đụng ca / đơn / thẻ thật: chép POS Profile thành 2 profile "ZZTEST Card ..." (A, M ở profile 1; B ở profile 2),
	user tạm A, B (POS CASHIER), K (POS KITCHEN), M (POS MANAGER); 2 thẻ bàn tạm "ZZT-<hash>-1/2" thuộc Branch của profile.
	Không đóng ca. Cuối hàm dọn mọi dữ liệu thử: commit trước mỗi lần xóa, thử lại 3 lần khi QueryDeadlockError,
	Contact trước User; lỗi dọn chỉ in WARN + lệnh xóa tay; dòng KẾT QUẢ luôn được in.
	Sau khi PASS: chạy lại check_draft_cancel(...), check_open_orders(...), run_order_qr_selftest(), run_order_history_selftest().
	Khách vãng lai (2026-11-24): đơn thử dùng Customer TẠM "ZZTEST WI ..." do script tự tạo và tự xóa — không cần POS Profile
	thật đã cấu hình Khách vãng lai, không dùng Customer thật nào.
	"""
	if pos_profile is None:  # không truyền dữ liệu -> tự dựng quán thử tạm (selfcheck/test_shop.py), dọn ở cuối
		from mypos.selfcheck.test_shop import zz_test_shop

		_shop = zz_test_shop("create", open_shift=False)
		if not _shop.get("ok"):
			print(f"SKIP: {_shop.get('reason')}")
			print("KẾT QUẢ: SKIP")
			return None
		try:
			return check_table_card(_shop["pos_profile"], _shop["item"], _shop["mop_cash"], _shop["price_list"])
		finally:
			zz_test_shop("drop", _shop["tag"])

	import time
	import traceback

	import frappe
	from frappe.utils import now_datetime, nowdate

	from mypos.mypos.api import pos_api as P

	PREFIX = "zz.test.card"
	PROFILE_PREFIX = "ZZTEST Card "
	WALK_IN_PREFIX = "ZZTEST WI Card "  # Customer khách vãng lai tạm (2026-11-24)
	CARD_PREFIX = "ZZT-"
	ROLE_OF = {"A": "POS CASHIER", "B": "POS CASHIER", "K": "POS KITCHEN", "M": "POS MANAGER"}
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
				delete_fresh("POS Profile", prof, removed, failed)
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
	def draft(order_type="Take Away", buzzer=None, key="A"):
		line = [{"item_code": item_code, "qty": 2, "options": []}]
		res, err = as_user(key, P.create_draft_order, line, order_type, mode_of_payment=mode_of_payment,
			price_list=ctx["price_list"], buzzer=buzzer)
		if err:
			raise err
		return res["invoice_name"]

	def paid(order_type="Take Away", buzzer=None, key="A"):
		name = draft(order_type, buzzer, key)
		_r, err = as_user(key, P.pay_cash, name)
		if err:
			raise err
		return name

	def card(name):
		"""Thẻ trong get_buzzers của A: {available, status, used_by} (status tính theo đơn)."""
		rows = as_user("A", P.get_buzzers)[0] or []
		return next((b for b in rows if b["name"] == name), None)

	def stored_status(name):
		return frappe.db.get_value("MYPOS Buzzer", name, "status")

	def queue(key):
		res, err = as_user(key, P.get_serve_queue)
		return res or [], err

	def in_queue(key, name):
		return any(o["name"] == name for o in queue(key)[0])

	def prepared(name):
		_r, err = as_user("K", P.set_kitchen_status, name, "Đã làm")
		if err:
			raise err

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
		# Khách vãng lai TẠM (2026-11-24): profile tạm dùng Customer ZZTEST, không dựa vào cấu hình của profile thật.
		wi = frappe.new_doc("Customer")
		wi.customer_name = f"{WALK_IN_PREFIX}{frappe.generate_hash(length=6)}"
		wi.customer_type = "Individual"
		wi.customer_group = frappe.db.get_single_value("Selling Settings", "customer_group") or "Individual"
		wi.territory = frappe.db.get_single_value("Selling Settings", "territory") or "All Territories"
		wi.insert(ignore_permissions=True)
		if not src.get("branch"):
			raise RuntimeError(f"POS Profile {pos_profile} chưa có Branch — thẻ bàn gắn theo Branch.")
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

		prof1 = make_profile(("A", "M"))
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
		tag = frappe.generate_hash(length=4).upper()
		cards = []
		for i in (1, 2):
			c = frappe.get_doc({"doctype": "MYPOS Buzzer", "buzzer_number": f"{CARD_PREFIX}{tag}-{i}",
				"branch": src.branch, "status": "Sẵn sàng"}).insert(ignore_permissions=True)
			cards.append(c.name)
		frappe.db.commit()
		c1, c2 = cards
		print(f"INFO profile {prof1} (A, M) / {prof2} (B), ca {shift}, thẻ {cards}")

		print("== 2. Dine In: gán thẻ, Đã làm vẫn giữ thẻ + thu ngân nhận thông báo ==")
		d1 = draft("Dine In", buzzer=c1)
		ok("2a Draft gán thẻ -> thẻ Đang dùng (theo đơn), used_by = đơn", card(c1) and not card(c1)["available"]
			and card(c1)["status"] == "Đang dùng" and card(c1)["used_by"] == d1, f"({card(c1)})")
		_r, err = as_user("A", P.create_draft_order, [{"item_code": item_code, "qty": 1, "options": []}], "Dine In",
			mode_of_payment=mode_of_payment, price_list=ctx["price_list"], buzzer=c1)
		blocked("2b Gán thẻ đang giữ cho đơn khác -> chặn, nêu 'thẻ bàn' + mã đơn", err, "thẻ bàn", d1)
		_r, err = as_user("A", P.pay_cash, d1)
		ok("2c Thanh toán -> status lưu của thẻ = Đang dùng", err is None and stored_status(c1) == "Đang dùng", f"({err})")
		ok("2d Chưa làm -> chưa vào hàng chờ phục vụ", not in_queue("A", d1))
		prepared(d1)
		ok("2e Đã làm -> thẻ vẫn giữ (Đang dùng, không trống)", stored_status(c1) == "Đang dùng" and not card(c1)["available"])
		rows, err = queue("A")
		row = next((o for o in rows if o["name"] == d1), None)
		number = frappe.db.get_value("MYPOS Buzzer", c1, "buzzer_number")
		ok("2f Cashier A (profile 1) thấy đơn: đúng số bàn, Dine In, khách vãng lai (is_walk_in) ẩn tên, 2 món, preview 'x2'",
			err is None and row and row["buzzer_number"] == number and row["order_type"] == "Dine In"
			and row["customer_name"] == "" and row.get("is_walk_in") is True
			and row["item_count"] == 2 and row["items_preview"]
			and row["items_preview"][0].endswith("x2") and row["waiting_seconds"] >= 0, f"({err or row})")
		ok("2g MANAGER M (cùng profile) cũng thấy", in_queue("M", d1))
		ok("2h Cashier B (profile 2) KHÔNG thấy đơn của profile 1", queue("B")[1] is None and not in_queue("B", d1),
			f"({queue('B')})")
		_r, err = queue("K")
		blocked("2i KITCHEN gọi get_serve_queue -> chặn", err, "không có quyền")

		print("== 3. Đã hoàn thành -> nhả thẻ, rời hàng chờ ==")
		_r, err = as_user("A", P.set_kitchen_status, d1, "Đã hoàn thành")
		ok("3a Đã làm -> Đã hoàn thành: thẻ Sẵn sàng NGAY (status lưu + trống), không cần thao tác khác",
			err is None and stored_status(c1) == "Sẵn sàng" and card(c1)["available"], f"({err}; {card(c1)})")
		ok("3b Rời hàng chờ (thông báo thu ngân)", not in_queue("A", d1))
		ok("3c Không còn API nhả thẻ thủ công (pos_api.confirm_pickup)", not hasattr(P, "confirm_pickup"))

		print("== 4. Hủy Draft (Cancelled) nhả thẻ ==")
		d2 = draft("Dine In", buzzer=c2)
		ok("4a Draft giữ thẻ 2", not card(c2)["available"])
		_r, err = as_user("A", P.cancel_draft_order, d2, 0, "Khách đổi ý")
		ok("4b Hủy -> docstatus 2, thẻ 2 trống, gán lại được",
			err is None and frappe.db.get_value("POS Invoice", d2, "docstatus") == 2 and card(c2)["available"], f"({err})")

		print("== 5. Manager xử lý đơn -> nhả thẻ, rời hàng chờ ==")
		p5 = paid("Dine In", buzzer=c1)
		prepared(p5)
		ok("5a Đơn Đã làm có trong hàng chờ, giữ thẻ", in_queue("A", p5) and not card(c1)["available"])
		_r, err = as_user("M", P.resolve_open_order, p5, "Không thực hiện được", "Hết sữa")
		ok("5b 'Không thực hiện được' (từ Đã làm) -> thẻ Sẵn sàng + trống, rời hàng chờ",
			err is None and stored_status(c1) == "Sẵn sàng" and card(c1)["available"] and not in_queue("A", p5), f"({err})")
		p6 = paid("Dine In", buzzer=c2)
		_r, err = as_user("M", P.resolve_open_order, p6, "Khách không nhận", "Khách bỏ về")
		ok("5c 'Khách không nhận' (từ Chưa làm) -> thẻ Sẵn sàng + trống",
			err is None and stored_status(c2) == "Sẵn sàng" and card(c2)["available"], f"({err})")
		p5d = paid("Dine In", buzzer=c1)
		prepared(p5d)
		inv = frappe.get_doc("POS Invoice", p5d)
		inv.flags.ignore_permissions = True
		inv.cancel()  # Administrator hủy đơn đã submit đang "Đã làm" (hook on_cancel)
		ok("5d Hủy đơn đã thanh toán đang 'Đã làm' -> thẻ Sẵn sàng (status lưu) + trống",
			stored_status(c1) == "Sẵn sàng" and card(c1)["available"], f"({card(c1)})")

		print("== 6. Thẻ kẹt 'Đang dùng' không còn đơn giữ ==")
		frappe.db.set_value("MYPOS Buzzer", c2, "status", "Đang dùng", update_modified=False)
		frappe.db.commit()
		info = card(c2)
		ok("6a get_buzzers: trống, status tính = Sẵn sàng", info["available"] and info["status"] == "Sẵn sàng", f"({info})")
		try:
			d6 = draft("Dine In", buzzer=c2)
			p6b_err = as_user("A", P.pay_cash, d6)[1]
			ok("6b Gán + thanh toán với thẻ kẹt -> không lỗi", p6b_err is None, f"({p6b_err})")
			as_user("M", P.resolve_open_order, d6, "Khách không nhận", "dọn thử")
		except Exception as e:  # noqa: BLE001
			ok("6b Gán + thanh toán với thẻ kẹt -> không lỗi", False, repr(e)[:150])

		print("== 7. Take Away Đã làm -> vào hàng chờ 'gọi khách', không thẻ ==")
		t7 = paid("Take Away")
		prepared(t7)
		row = next((o for o in queue("A")[0] if o["name"] == t7), None)
		ok("7a Take Away trong hàng chờ, buzzer_number None", row and row["order_type"] == "Take Away" and row["buzzer_number"] is None,
			f"({row})")
		as_user("A", P.set_kitchen_status, t7, "Đã hoàn thành")

		print("== 8. Đơn kênh QR Đã làm -> KHÔNG vào hàng chờ (khách tự tới quầy, luồng QR không đổi) ==")
		q8 = paid("Take Away")
		frappe.db.set_value("POS Invoice", q8, "order_channel", "QR", update_modified=False)
		frappe.db.commit()
		prepared(q8)
		ok("8a Đơn QR Đã làm không có trong get_serve_queue", not in_queue("A", q8))
		as_user("A", P.set_kitchen_status, q8, "Đã hoàn thành")
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
