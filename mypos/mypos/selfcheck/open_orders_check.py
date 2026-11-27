def check_open_orders(pos_profile=None, item_code=None, mode_of_payment=None, price_list=None):
	"""Đóng ca chặn đơn đã thanh toán chưa giao; trạng thái kết thúc có lý do; quản lý xử lý TỪNG đơn rồi mới đóng ca (2026-11-23).

	Dán CẢ hàm vào `bench --site <site> console` MỚI (SAU khi migrate) rồi gọi, ví dụ:
	    check_open_orders("POS TEST", "<mã món VARIANT>", "Cash", price_list="<Price List của MYPOS Menu>")

	KHÔNG đụng ca / đơn thật: chép POS Profile thành "ZZTEST Open ...", user tạm A (POS CASHIER), K (POS KITCHEN),
	M (POS MANAGER). Không submit phiếu đóng ca (chỉ chạy kiểm tra chặn đóng ca) -> không gộp hóa đơn thử thành Sales Invoice.
	Cuối hàm dọn mọi dữ liệu thử: commit trước mỗi lần xóa,
	thử lại 3 lần khi QueryDeadlockError, Contact trước User; lỗi dọn chỉ in WARN + lệnh xóa tay; dòng KẾT QUẢ luôn được in.
	Sau khi PASS: chạy lại check_draft_cancel(...), check_shift_owner(...), run_order_qr_selftest(), run_order_history_selftest().
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
			return check_open_orders(_shop["pos_profile"], _shop["item"], _shop["mop_cash"], _shop["price_list"])
		finally:
			zz_test_shop("drop", _shop["tag"])

	import time
	import traceback

	import frappe
	from frappe.utils import now_datetime, nowdate

	from mypos.mypos.api import pos_api as P
	from mypos.mypos.doctype.pos_invoice_hooks import kitchen_status as KS
	from mypos.mypos.doctype.pos_shift_hooks import pos_shift_hooks as H

	PREFIX = "zz.test.open"
	PROFILE_PREFIX = "ZZTEST Open "
	WALK_IN_PREFIX = "ZZTEST WI Open "  # Customer khách vãng lai tạm (2026-11-24)
	ROLE_OF = {"A": "POS CASHIER", "K": "POS KITCHEN", "M": "POS MANAGER"}
	DEADLOCK = getattr(frappe, "QueryDeadlockError", None) or getattr(frappe.exceptions, "QueryDeadlockError", ())
	results, users, ctx = [], {}, {"profile": None}

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

	def passed(case, err, extra=""):
		ok(case, err is None, (f"-> {type(err).__name__}: {str(err)[:140]}" if err else "") + extra)

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
				closings = frappe.get_all("POS Closing Entry", filters={"pos_profile": prof}, pluck="name")
				merges = frappe.get_all("POS Invoice Merge Log", filters={"pos_closing_entry": ["in", closings or [""]]},
					fields=["name", "consolidated_invoice"])
				for n in closings:
					delete_fresh("POS Closing Entry", n, removed, failed, cancel=True)
				for m in merges:
					delete_fresh("POS Invoice Merge Log", m.name, removed, failed, cancel=True)
					if m.consolidated_invoice:
						delete_fresh("Sales Invoice", m.consolidated_invoice, removed, failed, cancel=True)
				for dt in ("POS Invoice", "POS Opening Entry"):
					for n in frappe.get_all(dt, filters={"pos_profile": prof}, pluck="name"):
						delete_fresh(dt, n, removed, failed, cancel=True)
				delete_fresh("POS Profile", prof, removed, failed)
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
	def draft(order_type="Take Away", buzzer=None):
		line = [{"item_code": item_code, "qty": 1, "options": []}]
		res, err = as_user("A", P.create_draft_order, line, order_type, mode_of_payment=mode_of_payment,
			price_list=ctx["price_list"], buzzer=buzzer)
		if err:
			raise err
		return res["invoice_name"]

	def paid(order_type="Take Away", buzzer=None):
		name = draft(order_type, buzzer)
		_r, err = as_user("A", P.pay_cash, name)
		if err:
			raise err
		return name

	def st(name):
		return frappe.db.get_value("POS Invoice", name, ["custom_kitchen_status", "kitchen_done_by", "kitchen_done_at",
			"kitchen_completed_by", "kitchen_completed_at", "kitchen_outcome_reason", "docstatus", "custom_cancel_reason"], as_dict=True)

	def comments_of(name):
		return frappe.get_all("Comment", filters={"reference_doctype": "POS Invoice", "reference_name": name},
			pluck="content")

	def check_closing(key):
		from erpnext.accounts.doctype.pos_closing_entry.pos_closing_entry import make_closing_entry_from_opening

		closing = make_closing_entry_from_opening(frappe.get_doc("POS Opening Entry", ctx["shift"]))
		return as_user(key, H._check_closing, closing)

	def cancel_paid(name):
		doc = frappe.get_doc("POS Invoice", name)
		if doc.docstatus == 1:
			doc.flags.ignore_permissions = True
			doc.cancel()

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
		ctx["price_list"] = price_list or src.get("selling_price_list")
		modes = [p.mode_of_payment for p in (src.get("payments") or []) if p.mode_of_payment] or [mode_of_payment]
		for key, role in ROLE_OF.items():
			email = f"{PREFIX}.{key.lower()}@example.com"
			frappe.get_doc({"doctype": "User", "email": email, "first_name": f"ZZTEST {key}",
				"user_type": "System User", "send_welcome_email": 0, "enabled": 1,
				"roles": [{"role": role}]}).insert(ignore_permissions=True)
			users[key] = email
		prof = frappe.copy_doc(src)
		prof.set("__newname", f"{PROFILE_PREFIX}{frappe.generate_hash(length=6)}")
		prof.set("custom_walk_in_customer", wi.name)
		prof.disabled = 0
		prof.set("applicable_for_users", [])
		for key in ("A", "M"):
			prof.append("applicable_for_users", {"user": users[key], "default": 0})
		# 2026-11-25: mỗi Branch tối đa 1 profile đang bật (pos_profile_hooks). Profile tạm cùng Branch với profile thật
		# -> bật cờ chỉ dùng cho self-test (không đặt được từ Desk/API).
		prof.flags.mypos_allow_shared_branch = True
		prof.insert(ignore_permissions=True)
		ctx["profile"] = prof.name

		def open_shift():
			doc = frappe.get_doc({"doctype": "POS Opening Entry", "pos_profile": prof.name, "company": src.company,
				"user": users["A"], "period_start_date": now_datetime(), "posting_date": nowdate(),
				"balance_details": [{"mode_of_payment": m, "opening_amount": 0} for m in modes]})
			doc.insert(ignore_permissions=True)
			doc.submit()
			return doc.name

		ctx["shift"], err = as_user("A", open_shift)
		if err:
			raise err
		print(f"INFO profile {prof.name}, ca {ctx['shift']}")

		print("== 2. Chặn đóng ca theo trạng thái pha chế + người/giờ ==")
		p1 = paid()
		ok("2a Thu tiền xong: 'Chưa làm'", st(p1).custom_kitchen_status == "Chưa làm")
		_r, err = check_closing("A")
		blocked("2b 'Chưa làm' -> chặn, nêu 'chưa pha chế' + mã", err, "chưa pha chế", p1)
		_r, err = as_user("K", P.set_kitchen_status, p1, "Đã làm")
		s1 = st(p1)
		ok("2c KITCHEN bấm Đã làm -> ghi kitchen_done_by/at = K", err is None and s1.kitchen_done_by == users["K"] and s1.kitchen_done_at,
			f"({err or s1})")
		_r, err = check_closing("A")
		blocked("2d 'Đã làm' -> chặn, nêu 'đã làm, chưa giao' + mã", err, "đã làm, chưa giao", p1)
		_r, err = as_user("A", P.set_kitchen_status, p1, "Đã hoàn thành")
		s1 = st(p1)
		ok("2e CASHIER bấm Đã hoàn thành -> ghi kitchen_completed_by/at = A",
			err is None and s1.kitchen_completed_by == users["A"] and s1.kitchen_completed_at, f"({err or s1})")
		_r, err = check_closing("A")
		passed("2f 'Đã hoàn thành' -> không chặn", err)

		print("== 3. resolve_open_order ==")
		p2 = paid()
		_r, err = as_user("A", P.resolve_open_order, p2, "Khách không nhận")
		blocked("3a 'Khách không nhận' thiếu lý do -> từ chối", err, "nhập lý do")
		_r, err = as_user("A", P.resolve_open_order, p2, "Khách không nhận", "Gọi 3 lần không ai nhận")
		s2 = st(p2)
		ok("3b 'Khách không nhận' có lý do -> lý do xử lý pha chế, người/giờ, comment",
			err is None and s2.custom_kitchen_status == "Khách không nhận" and "Gọi 3 lần" in (s2.kitchen_outcome_reason or "")
			and s2.kitchen_completed_by == users["A"] and any("Kết thúc đơn" in (c or "") for c in comments_of(p2)), f"({err or s2})")
		_r, err = as_user("K", P.set_kitchen_status, p2, "Đã làm")
		blocked("3c set_kitchen_status trên đơn đã kết thúc -> từ chối", err, "đã kết thúc")
		_r, err = check_closing("A")
		passed("3d Đơn 'Khách không nhận' không chặn đóng ca", err)
		p3 = paid()
		_r, err = as_user("A", P.resolve_open_order, p3, "Đã hoàn thành")
		blocked("3e 'Đã hoàn thành' từ 'Chưa làm' thiếu lý do -> từ chối", err, "nhập lý do")
		_r, err = as_user("A", P.resolve_open_order, p3, "Đã hoàn thành", "Giao luôn bánh có sẵn")
		ok("3f 'Đã hoàn thành' từ 'Chưa làm' có lý do -> OK, lý do lưu",
			err is None and st(p3).custom_kitchen_status == "Đã hoàn thành" and "Giao luôn" in (st(p3).kitchen_outcome_reason or ""), f"({err})")
		p4 = paid()
		as_user("K", P.set_kitchen_status, p4, "Đã làm")
		_r, err = as_user("A", P.resolve_open_order, p4, "Đã hoàn thành")
		passed("3g 'Đã hoàn thành' từ 'Đã làm' không cần lý do", err)
		p5 = paid()
		_r, err = as_user("M", P.resolve_open_order, p5, "Không thực hiện được", "Hết nguyên liệu")
		ok("3h MANAGER 'Không thực hiện được' -> OK, người kết thúc = M", err is None and st(p5).kitchen_completed_by == users["M"]
			and st(p5).custom_kitchen_status == "Không thực hiện được", f"({err})")
		p6 = paid()
		_r, err = as_user("K", P.resolve_open_order, p6, "Khách không nhận", "x")
		blocked("3i KITCHEN gọi resolve -> chặn", err, "không có quyền")
		_r, err = as_user("A", P.resolve_open_order, p6, "Đã đóng ca chưa xử lý", "x")
		blocked("3j Kết quả ngoài danh sách -> từ chối", err, "kết quả không hợp lệ")
		_r, err = as_user("A", P.resolve_open_order, p1, "Khách không nhận", "x")
		blocked("3k Đơn đã kết thúc -> từ chối", err, "đã kết thúc")

		print("== 4. Không còn xử lý hàng loạt ==")
		ok("4a pos_api không còn resolve_open_orders / force_close_shift",
			not hasattr(P, "resolve_open_orders") and not hasattr(P, "force_close_shift"))
		ok("4b kitchen_status không còn hàng đợi 'Cần xử lý' (review_orders) / cờ Cần xem lại",
			not hasattr(KS, "review_orders") and not hasattr(KS, "NEEDS_REVIEW_STATUSES")
			and "Đã đóng ca chưa xử lý" not in KS.KITCHEN_TERMINAL_STATUSES)

		print("== 5. Thẻ bàn nhả khi kết thúc ==")
		bz = [b for b in (as_user("A", P.get_buzzers)[0] or []) if b.get("available")]
		pd = None
		if not bz:
			print("SKIP 5: chi nhánh không có thẻ bàn đang trống")
		else:
			bname = bz[0]["name"]
			pd = paid("Dine In", buzzer=bname)
			ok("5a Đơn Dine In đã thanh toán giữ thẻ (Đang dùng)", frappe.db.get_value("MYPOS Buzzer", bname, "status") == "Đang dùng")
			as_user("A", P.resolve_open_order, pd, "Khách không nhận", "Khách bỏ về")
			free = [b for b in as_user("A", P.get_buzzers)[0] if b["name"] == bname][0]
			ok("5b 'Khách không nhận' -> thẻ Sẵn sàng + trống", frappe.db.get_value("MYPOS Buzzer", bname, "status") == "Sẵn sàng"
				and free["available"], f"({free})")

		print("== 6. Quản lý xử lý từng đơn rồi đóng ca (không còn đóng ca bắt buộc) ==")
		for name in (p1, p2, p3, p4, p5, p6, pd):
			if name:
				cancel_paid(name)  # các đơn trên đã xong, hủy cho gọn ca thử
		d1 = draft()
		p8 = paid()
		_r, err = check_closing("A")
		blocked("6a Còn Draft + đơn 'Chưa làm' -> chặn đóng ca", err, "chưa thanh toán", d1, p8)
		ok("6b Thông báo chặn không còn nhắc 'Đóng ca bắt buộc'", err is not None and "bắt buộc" not in str(err).lower())
		_r, err = as_user("M", P.cancel_draft_order, d1, 0, "Khách không lấy")
		s_d1 = st(d1)
		ok("6c MANAGER hủy Draft có lý do -> Cancelled, 'Thủ công: Khách không lấy'",
			err is None and s_d1.docstatus == 2 and (s_d1.custom_cancel_reason or "").startswith("Thủ công: Khách không lấy"), f"({err or s_d1})")
		_r, err = as_user("M", P.resolve_open_order, p8, "Không thực hiện được", "Hết sữa")
		ok("6d MANAGER xử lý đơn 'Chưa làm' có lý do", err is None and st(p8).custom_kitchen_status == "Không thực hiện được", f"({err})")
		_r, err = check_closing("A")
		passed("6e Đã xử lý hết -> đóng ca không bị chặn (đơn Cancelled không tính)", err)
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
				+ (frappe.get_all("POS Invoice", filters={"pos_profile": ctx["profile"]}, pluck="name") if ctx["profile"] else [])
			ok("7 Dọn dữ liệu: không còn profile / user / đơn thử trong DB", not left, f"({left})")
		except Exception:  # noqa: BLE001
			ok("7 Dọn dữ liệu (lỗi khi dọn — xem WARN / traceback)", False)
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
