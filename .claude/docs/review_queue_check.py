def check_review_queue(pos_profile, item_code, mode_of_payment, price_list=None):
	"""Xử lý đơn cần xem lại trên Desk (máy POS không đổi): kitchen_status.review_orders / review_counts, luồng xem lại của
	resolve_open_order(s), Script Report "MYPOS Review Queue", thông báo cho quản lý chi nhánh, thông điệp khách có số liên hệ.

	Dán CẢ hàm vào `bench --site <site> console` MỚI (SAU khi migrate) rồi gọi, ví dụ:
	    check_review_queue("POS TEST", "CH-CFLON", "Cash", price_list="<Price List của MYPOS Menu>")

	KHÔNG đụng ca / đơn thật: chép POS Profile thành "ZZTEST Review ...", user tạm A (POS CASHIER), K (POS KITCHEN),
	M (POS MANAGER, thuộc Applicable for Users), M2 (POS MANAGER, KHÔNG thuộc). Trạng thái đơn / "đã gộp" / tuổi đơn giả lập
	bằng db.set_value. Job nhắc chỉ chạy cho profile tạm (remind_overdue_reviews(pos_profile)). Branch.brand_phone / brand_name
	đổi tạm rồi TRẢ LẠI trong finally. Trước khi đóng ca bắt buộc, các đơn thử đã thanh toán được hủy để phiếu đóng ca không gộp
	hóa đơn thử. Có commit (job nhắc, ERPNext khi submit phiếu đóng ca) -> cuối hàm dọn mọi dữ liệu thử (commit trước mỗi lần xóa,
	thử lại khi QueryDeadlockError, Contact trước User); lỗi dọn chỉ in WARN + lệnh xóa tay; dòng KẾT QUẢ luôn được in.
	Sau khi PASS: chạy lại check_open_orders(...), check_draft_cancel(...), check_shift_owner(...), run_order_qr_selftest(),
	run_order_history_selftest().
	"""
	import time
	import traceback

	import frappe
	from frappe.utils import add_to_date, now_datetime, nowdate

	from leescoffee_pos.leescoffee_pos.api import customer_order_api as C
	from leescoffee_pos.leescoffee_pos.api import pos_api as P
	from leescoffee_pos.leescoffee_pos.doctype.pos_invoice_hooks import kitchen_status as KS

	PREFIX = "zz.test.review"
	PROFILE_PREFIX = "ZZTEST Review "
	FAKE_SI = "ZZTEST-SI-FAKE"
	REPORT = "MYPOS Review Queue"
	LOG = "MYPOS Order Cancel Log"
	ROLE_OF = {"A": "POS CASHIER", "K": "POS KITCHEN", "M": "POS MANAGER", "M2": "POS MANAGER"}
	DEADLOCK = getattr(frappe, "QueryDeadlockError", None) or getattr(frappe.exceptions, "QueryDeadlockError", ())
	results, users, ctx = [], {}, {"profile": None, "branch": None, "brand": None}

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

	def blocked(case, err, *phrases, exc=None):
		text = str(err or "").lower()
		good = err is not None and all(ph.lower() in text for ph in phrases) and (exc is None or isinstance(err, exc))
		ok(case, good, f"-> {type(err).__name__}: {str(err)[:140]}" if err else "-> KHÔNG bị chặn")

	# ---------------- dọn dữ liệu thử ----------------
	def delete_fresh(dt, name, removed, failed, cancel=False):
		last = None
		for _attempt in range(3):
			try:
				frappe.db.commit()
				if not frappe.db.exists(dt, name):
					return
				if dt == "POS Invoice" and frappe.db.get_value(dt, name, "consolidated_invoice") == FAKE_SI:
					frappe.db.set_value(dt, name, {"consolidated_invoice": None, "status": "Paid"}, update_modified=False)
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
				invoices = frappe.get_all("POS Invoice", filters={"pos_profile": prof}, pluck="name")
				for nl in frappe.get_all("Notification Log", filters={"document_type": ["in", ["POS Invoice", "POS Closing Entry"]],
						"document_name": ["in", (invoices + closings) or [""]]}, pluck="name"):
					delete_fresh("Notification Log", nl, removed, failed)
				for n in invoices:
					delete_fresh("POS Invoice", n, removed, failed, cancel=True)
				for n in frappe.get_all("POS Opening Entry", filters={"pos_profile": prof}, pluck="name"):
					delete_fresh("POS Opening Entry", n, removed, failed, cancel=True)
				for log in frappe.get_all(LOG, filters={"pos_profile": prof}, pluck="name"):
					delete_fresh(LOG, log, removed, failed)
				delete_fresh("POS Profile", prof, removed, failed)
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
	def paid():
		line = [{"item_code": item_code, "qty": 1, "options": []}]
		res, err = as_user("A", P.create_draft_order, line, "Take Away", mode_of_payment=mode_of_payment,
			price_list=ctx["price_list"])
		if err:
			raise err
		_r, err = as_user("A", P.pay_cash, res["invoice_name"])
		if err:
			raise err
		return res["invoice_name"]

	def set_inv(name, **values):
		frappe.db.set_value("POS Invoice", name, values, update_modified=False)

	def st(name):
		return frappe.db.get_value("POS Invoice", name, ["custom_kitchen_status", "needs_review", "kitchen_outcome_reason",
			"kitchen_completed_by"], as_dict=True)

	def review_names():
		rows = KS.review_orders(ctx["profile"], limit=200)
		return [r["name"] for r in rows], rows, None

	def notes(user, doctype, name):
		return frappe.get_all("Notification Log", filters={"for_user": user, "document_type": doctype, "document_name": name},
			pluck="name")

	def customer_view(name, s):
		rows = frappe.get_all("POS Invoice", filters={"name": name}, fields=C._ORDER_FIELDS)
		payload = C._orders_payload(s, rows, {name: "active"})[0]
		active = C._is_active_paid(rows[0], add_to_date(now_datetime(), hours=-C.ACTIVE_PAID_HOURS))
		return payload, active

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
		prof.disabled = 0
		prof.set("applicable_for_users", [])
		for key in ("A", "M"):
			prof.append("applicable_for_users", {"user": users[key], "default": 0})
		prof.insert(ignore_permissions=True)
		ctx["profile"] = prof.name
		ctx["branch"] = prof.get("branch")
		if ctx["branch"]:
			ctx["brand"] = frappe.db.get_value("Branch", ctx["branch"], ["brand_name", "brand_phone"], as_dict=True)

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
		print(f"INFO profile {prof.name}, ca {ctx['shift']}, branch {ctx['branch']}")

		print("== 2. Hàng đợi 'Cần xử lý' ==")
		q1, q2, q3, q4 = paid(), paid(), paid(), paid()
		as_user("A", P.resolve_open_order, q1, "Khách không nhận", "Gọi không ai nhận")
		set_inv(q2, custom_kitchen_status=KS.SHIFT_CLOSED, needs_review=1, status="Consolidated", consolidated_invoice=FAKE_SI)
		as_user("A", P.resolve_open_order, q3, "Không thực hiện được", "Hết nguyên liệu")
		set_inv(q3, creation=add_to_date(now_datetime(), hours=-25))
		names, rows, err = review_names()
		ok("2a review_orders có đơn needs_review + 'Đã đóng ca chưa xử lý', không có đơn đang làm",
			err is None and {q1, q2, q3} <= set(names) and q4 not in names, f"({err or names})")
		ok("2b Đơn đã gộp (Consolidated) vẫn hiện", q2 in names)
		ok("2c Cũ nhất trước + age_minutes", names and names[0] == q3 and rows[0]["age_minutes"] >= 25 * 60, f"({names[:1]})")
		ok("2d Trả lý do đã lưu trên đơn", any(r["name"] == q3 and "Hết nguyên liệu" in (r.get("kitchen_outcome_reason") or "")
			for r in rows or []))
		ok("2e Máy POS không đổi: get_orders không có scope 'review'", "review" not in P.ORDER_SCOPES, f"({P.ORDER_SCOPES})")

		print("== 3. Bộ đếm ==")
		cnt = KS.review_counts(prof.name)
		ok("3a review_counts: review = 3, overdue = 1 (đơn lùi 25 giờ)", cnt == {"review": 3, "overdue": 1}, f"({cnt})")
		over = [r["name"] for r in KS.review_orders(prof.name, overdue_only=True)]
		ok("3b review_orders(overdue_only) chỉ có đơn quá 24 giờ", over == [q3], f"({over})")

		print("== 4. Script Report ==")
		from frappe.desk.query_report import run as run_report

		res, err = as_user("M", run_report, REPORT, {"pos_profile": prof.name})
		got = {r.get("name") for r in (res or {}).get("result", []) if isinstance(r, dict)}
		ok("4a MANAGER chạy Report -> đúng đơn cần xử lý", err is None and {q1, q2, q3} <= got and q4 not in got,
			f"({err or got})")
		_r, err = as_user("A", run_report, REPORT, {"pos_profile": prof.name})
		ok("4b CASHIER chạy Report -> bị chặn", err is not None, f"({type(err).__name__}: {str(err)[:100]})")
		_r, err = as_user("K", run_report, REPORT, {})
		ok("4c KITCHEN chạy Report -> bị chặn", err is not None, f"({type(err).__name__})")

		print("== 5. Xử lý từng đơn (luồng xem lại) ==")
		_r, err = as_user("M", P.resolve_open_order, q1, "Đã hoàn thành")
		blocked("5a Thiếu lý do -> từ chối", err, "nhập lý do")
		_r, err = as_user("A", P.resolve_open_order, q1, "Đã hoàn thành", "x")
		blocked("5b CASHIER xử lý đơn cần xem lại -> chặn", err, "chỉ quản lý", exc=frappe.PermissionError)
		_r, err = as_user("M", P.resolve_open_order, q1, "Hoàn tiền", "x")
		blocked("5c Kết cục ngoài danh sách -> từ chối", err, "kết quả không hợp lệ")
		_r, err = as_user("M", P.resolve_open_order, q1, "Đã hoàn thành", "Khách quay lại nhận")
		s1 = st(q1)
		names, _rows, _e = review_names()
		ok("5d MANAGER 'Đã hoàn thành' -> needs_review 0, rời danh sách, ghi người + lý do",
			err is None and s1.custom_kitchen_status == "Đã hoàn thành" and not s1.needs_review and q1 not in names
			and s1.kitchen_completed_by == users["M"] and "Khách quay lại" in (s1.kitchen_outcome_reason or ""), f"({err or s1})")
		ok("5e Comment 'Quản lý xử lý' trên đơn", any("Quản lý xử lý" in (c or "") for c in frappe.get_all("Comment",
			filters={"reference_doctype": "POS Invoice", "reference_name": q1}, pluck="content")))

		print("== 6. Xử lý hàng loạt ==")
		_r, err = as_user("M", P.resolve_open_orders, [q2, q1], "Khách không nhận", "Lô thử")
		ok("6a Một đơn lỗi (đã xử lý) -> báo lỗi, đơn còn lại giữ nguyên",
			err is not None and st(q2).custom_kitchen_status == KS.SHIFT_CLOSED and st(q2).needs_review, f"({err})")
		res, err = as_user("M", P.resolve_open_orders, frappe.as_json([q2, q3]), "Không thực hiện được", "Đã hoàn tiền")
		names, _rows, _e = review_names()
		ok("6b Lô hợp lệ (gồm đơn đã gộp) -> needs_review 0, danh sách rỗng",
			err is None and not st(q2).needs_review and not st(q3).needs_review and not ({q2, q3} & set(names)), f"({err or names})")

		print("== 7. Khách thấy gì ==")
		s = frappe._dict(display_name="ZZTEST", branch=ctx["branch"])
		q5 = paid()
		as_user("A", P.resolve_open_order, q5, "Không thực hiện được", "Máy hỏng")
		if ctx["branch"]:
			frappe.db.set_value("Branch", ctx["branch"], {"brand_phone": "0900 000 111", "brand_name": "ZZ Quán Thử"})
			view, active = customer_view(q5, s)
			msg = view.get("stage_message", "")
			ok("7a Có số: thông điệp có tên quán + số + mã đơn, nhóm active",
				"ZZ Quán Thử" in msg and "0900 000 111" in msg and q5 in msg and active, f"({msg}; active={active})")
			frappe.db.set_value("Branch", ctx["branch"], {"brand_phone": ""})
			view, _a = customer_view(q5, s)
			ok("7b Không có số -> câu cũ 'liên hệ quầy'", "liên hệ quầy" in view.get("stage_message", ""), f"({view.get('stage_message')})")
			internal = {"needs_review", "kitchen_outcome_reason", "kitchen_completed_by", "kitchen_done_by", "custom_kitchen_status"}
			ok("7c Không trả trường nội bộ, kitchen_status rỗng", not (internal & set(view)) and view.get("kitchen_status") == ""
				and "Máy hỏng" not in frappe.as_json(view))
		else:
			print("SKIP 7a-7c: POS Profile không có Branch")
		as_user("M", P.resolve_open_order, q5, "Không thực hiện được", "Đã hoàn tiền cho khách")
		view, active = customer_view(q5, s)
		ok("7d Đã giải quyết -> khách thấy 'Không thực hiện được', không còn active (trang khách ngừng poll)",
			view["stage"] == "failed" and not active, f"({view['stage']}, active={active})")

		print("== 8. Job nhắc quá 24 giờ ==")
		q6 = paid()
		set_inv(q6, custom_kitchen_status=KS.SHIFT_CLOSED, needs_review=1, creation=add_to_date(now_datetime(), hours=-26))
		KS.remind_overdue_reviews(pos_profile=prof.name)
		n_m, n_m2 = notes(users["M"], "POS Invoice", q6), notes(users["M2"], "POS Invoice", q6)
		ok("8a Gửi quản lý của chi nhánh (M), không gửi quản lý ngoài (M2)", len(n_m) == 1 and not n_m2, f"(M {len(n_m)}, M2 {len(n_m2)})")
		KS.remind_overdue_reviews(pos_profile=prof.name)
		ok("8b Chạy lại trong 24 giờ -> không nhắc lặp", len(notes(users["M"], "POS Invoice", q6)) == 1)

		print("== 9. Đóng ca bắt buộc -> thông báo ==")
		for name in (q1, q2, q3, q4, q5, q6):
			if frappe.db.get_value("POS Invoice", name, "consolidated_invoice") == FAKE_SI:
				set_inv(name, consolidated_invoice=None, status="Paid")
			doc = frappe.get_doc("POS Invoice", name)
			if doc.docstatus == 1:
				doc.flags.ignore_permissions = True
				doc.cancel()  # để phiếu đóng ca không gộp đơn thử thành Sales Invoice
		res, err = as_user("M", P.force_close_shift, ctx["shift"], "Thử thông báo")
		ce = (res or {}).get("closing_entry")
		ok("9a Đóng ca bắt buộc OK", err is None and ce, f"({err or res})")
		if ce:
			ok("9b Notification Log cho M, không cho M2", notes(users["M"], "POS Closing Entry", ce)
				and not notes(users["M2"], "POS Closing Entry", ce))
	except Exception:
		ok("Lỗi ngoài dự kiến", False)
		traceback.print_exc()
	finally:
		try:
			frappe.set_user("Administrator")
			frappe.db.rollback()
			if ctx["branch"] and ctx["brand"] is not None:
				frappe.db.set_value("Branch", ctx["branch"], {"brand_phone": ctx["brand"].brand_phone,
					"brand_name": ctx["brand"].brand_name})
				frappe.db.commit()
				print(f"INFO đã trả lại Branch {ctx['branch']}: brand_name / brand_phone")
			removed, failed = purge_leftovers()
			report_cleanup(removed, failed, "cuối")
			frappe.db.commit()
			left = frappe.get_all("POS Profile", filters={"name": ["like", PROFILE_PREFIX + "%"]}, pluck="name") \
				+ frappe.get_all("User", filters={"name": ["like", PREFIX + ".%"]}, pluck="name")
			ok("10 Dọn dữ liệu: không còn profile / user thử, Branch như cũ", not left and (not ctx["branch"] or ctx["brand"] is None
				or frappe.db.get_value("Branch", ctx["branch"], "brand_phone") == ctx["brand"].brand_phone), f"({left})")
		except Exception:  # noqa: BLE001
			ok("10 Dọn dữ liệu (lỗi khi dọn — xem WARN / traceback)", False)
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
