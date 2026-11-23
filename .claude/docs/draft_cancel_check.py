def check_draft_cancel(pos_profile, item_code, mode_of_payment, price_list=None):
	"""Chặn đóng ca khi còn Draft, tự hủy Draft quá hạn, hủy = Cancelled + lý do, tiền về sau khi hủy (2026-11-23).

	Dán CẢ hàm vào `bench --site <site> console` MỚI (SAU khi migrate) rồi gọi, ví dụ:
	    check_draft_cancel("POS TEST", "CH-CFLON", "Cash", price_list="<Price List của MYPOS Menu>")

	KHÔNG đụng ca / đơn thật: chép POS Profile thành "ZZTEST Draft ...", user tạm A (POS CASHIER), M (POS MANAGER).
	Job tự hủy được kiểm bằng hàm chọn đơn của job (`_stale_drafts`) rồi chỉ hủy đơn thử (`_cancel_batch`) — không hủy Draft thật.
	Đơn QR được giả lập: Draft tạo ở /pos rồi đổi order_channel = "QR" + payment_code. Webhook cần Branch có sepay_api_key
	(không có -> SKIP mục webhook). Lùi `creation` bằng db.set_value.
	Hủy đơn KHÔNG xóa: đơn chuyển docstatus 2 / "Cancelled", lý do ở custom_cancel_reason (tiền tố nguồn), Comment trên đơn.
	Có commit (job hủy commit từng đơn) -> cuối hàm dọn mọi dữ liệu thử: commit trước mỗi lần xóa, thử lại 3 lần khi
	QueryDeadlockError, Contact trước User; lỗi dọn chỉ in WARN + lệnh xóa tay; dòng KẾT QUẢ luôn được in.
	Sau khi PASS: chạy lại check_shift_owner(...), run_order_qr_selftest(), run_order_history_selftest().
	"""
	import time
	import traceback

	import frappe
	from frappe.utils import add_to_date, flt, now_datetime, nowdate
	from frappe.utils.password import get_decrypted_password
	from werkzeug.test import EnvironBuilder
	from werkzeug.wrappers import Request

	from leescoffee_pos.leescoffee_pos.api import pos_api as P
	from leescoffee_pos.leescoffee_pos.doctype.pos_invoice_hooks import order_cancel as OC
	from leescoffee_pos.leescoffee_pos.doctype.pos_shift_hooks import pos_shift_hooks as H
	from leescoffee_pos.leescoffee_pos.doctype.sepay import sepay as S

	PREFIX = "zz.test.draft"
	PROFILE_PREFIX = "ZZTEST Draft "
	ROLE_OF = {"A": "POS CASHIER", "M": "POS MANAGER"}
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

	def blocked(case, err, phrase):
		ok(case, err is not None and phrase.lower() in str(err).lower(),
			f"-> {type(err).__name__}: {str(err)[:120]}" if err else "-> KHÔNG bị chặn")

	def passed(case, err, extra=""):
		ok(case, err is None, (f"-> {type(err).__name__}: {str(err)[:120]}" if err else "") + extra)

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
				for inv in frappe.get_all("POS Invoice", filters={"pos_profile": prof}, pluck="name"):
					for nl in frappe.get_all("Notification Log", filters={"document_type": "POS Invoice", "document_name": inv}, pluck="name"):
						delete_fresh("Notification Log", nl, removed, failed)
				for dt in ("POS Closing Entry", "POS Invoice", "POS Opening Entry"):
					for n in frappe.get_all(dt, filters={"pos_profile": prof}, pluck="name"):
						delete_fresh(dt, n, removed, failed, cancel=True)
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
	def draft(order_type="Take Away", buzzer=None):
		line = [{"item_code": item_code, "qty": 1, "options": []}]
		res, err = as_user("A", P.create_draft_order, line, order_type, mode_of_payment=mode_of_payment,
			price_list=ctx["price_list"], buzzer=buzzer)
		if err:
			raise err
		return res["invoice_name"]

	def age(name, minutes):
		frappe.db.set_value("POS Invoice", name, "creation", add_to_date(now_datetime(), minutes=-minutes), update_modified=False)

	def as_qr(name, minutes):
		code = f"ZZTEST-{frappe.generate_hash(length=10).upper()}"
		frappe.db.set_value("POS Invoice", name, {"order_channel": "QR", "payment_code": code,
			"payment_status": "Chưa thanh toán"}, update_modified=False)
		age(name, minutes)
		return code

	def check_closing(key):
		from erpnext.accounts.doctype.pos_closing_entry.pos_closing_entry import make_closing_entry_from_opening

		closing = make_closing_entry_from_opening(frappe.get_doc("POS Opening Entry", ctx["shift"]))
		return as_user(key, H._check_closing, closing)

	def inv(name):
		return frappe.db.get_value("POS Invoice", name, ["name", "docstatus", "status", "custom_cancel_reason", "payment_code",
			"custom_late_payment", "custom_late_payment_ref", "sepay_payment_log"], as_dict=True)

	def is_cancelled(name, prefix):
		row = inv(name)
		return bool(row and row.docstatus == 2 and row.status == "Cancelled" and (row.custom_cancel_reason or "").startswith(prefix))

	def children_cancelled(name):
		bad = []
		for df in frappe.get_meta("POS Invoice").get_table_fields():
			if frappe.db.exists(df.options, {"parent": name, "parenttype": "POS Invoice", "docstatus": ["!=", 2]}):
				bad.append(df.options)
		return not bad, bad

	def comments(name):
		return frappe.get_all("Comment", filters={"reference_doctype": "POS Invoice", "reference_name": name}, pluck="content")

	def webhook(code, amount, tid):
		env = EnvironBuilder(method="POST", path="/api/method/leescoffee_pos.leescoffee_pos.doctype.sepay.sepay.sepay_webhook",
			json={"content": code, "transferAmount": flt(amount), "id": tid, "transferType": "in", "gateway": "TEST"},
			headers={"Authorization": f"Apikey {ctx['api_key']}"}).get_environ()
		old_req = getattr(frappe.local, "request", None)
		frappe.local.request = Request(env)
		frappe.local.request_ip = "127.0.0.1"
		frappe.set_user("Guest")
		try:
			return S.sepay_webhook(), None
		except Exception as e:  # noqa: BLE001
			frappe.clear_messages()
			return None, e
		finally:
			frappe.set_user("Administrator")
			frappe.local.request = old_req

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
		branch = prof.get("branch")
		ctx["api_key"] = get_decrypted_password("Branch", branch, "sepay_api_key", raise_exception=False) if branch else None
		print(f"INFO profile {prof.name}, ca {ctx['shift']}, branch {branch}, webhook {'có key' if ctx['api_key'] else 'SKIP (không có key)'}")

		print("== 2. Chặn đóng ca khi còn Draft ==")
		d1 = draft()
		_r, err = check_closing("A")
		blocked("2a Còn Draft POS -> chặn, nêu mã đơn", err, d1)
		ok("2b Thông báo tiếng Việt 'Còn … đơn chưa thanh toán'", err is not None and "chưa thanh toán" in str(err))

		print("== 3. Hủy tay (cancel_draft_order) ==")
		_r, err = as_user("A", P.cancel_draft_order, d1, 0, "")
		blocked("3a Lý do rỗng -> từ chối", err, "chọn lý do")
		_r, err = as_user("A", P.cancel_draft_order, d1, 0, "Khác", "")
		blocked("3b 'Khác' thiếu ghi chú -> từ chối", err, "nhập ghi chú")
		_r, err = as_user("A", P.cancel_draft_order, d1, 0, "Đặt nhầm")
		ok("3c Lý do hợp lệ -> đơn CÒN, Cancelled, lý do 'Thủ công: Đặt nhầm'",
			err is None and is_cancelled(d1, "Thủ công: Đặt nhầm"), f"({err or inv(d1)})")
		good, bad = children_cancelled(d1)
		ok("3c2 Bảng con của đơn cũng docstatus 2", good, f"({bad})")
		ok("3c3 Comment 'Hủy đơn' ghi người hủy A", any("Hủy đơn" in (c or "") and users["A"] in (c or "") for c in comments(d1)))
		_r, err = as_user("A", P.cancel_draft_order, d1, 0, "Đặt nhầm")
		blocked("3c4 Hủy lại đơn đã hủy -> từ chối", err, "đã thanh toán")
		_r, err = as_user("A", P.pay_cash, d1)
		blocked("3c5 Thu tiền đơn đã hủy -> từ chối", err, "không ở trạng thái draft")
		d1b = draft()
		_r, err = as_user("A", P.cancel_draft_order, d1b, 0, "Khác", "Khách gọi lại sau")
		ok("3c6 'Khác' + ghi chú -> 'Thủ công: Khác — Khách gọi lại sau'",
			err is None and is_cancelled(d1b, "Thủ công: Khác — Khách gọi lại sau"), f"({err or inv(d1b)})")
		orders, _e = as_user("A", P.get_orders, "all", 200)
		ok("3c7 Orders (ca hiện tại) không còn hiện đơn đã hủy",
			orders is not None and not {o["name"] for o in orders} & {d1, d1b})
		_r, err = check_closing("A")
		passed("3d Hết Draft -> đóng ca không bị chặn", err)

		print("== 4. Đơn đã thanh toán (pha chế chưa xong) không chặn ==")
		p1 = draft()
		_r, err = as_user("A", P.pay_cash, p1)
		passed("4a Thu tiền mặt", err)
		ok("4b Đơn Paid, bếp 'Chưa làm'", frappe.db.get_value("POS Invoice", p1, "custom_kitchen_status") == "Chưa làm")
		_r, err = check_closing("A")
		passed("4c Chỉ còn đơn Paid chưa pha chế -> không chặn", err)
		cancel_paid(p1)  # tránh gộp hóa đơn khi đóng ca thật ở mục 8

		print("== 5. Draft QR: trong hạn chặn, quá 15 phút không chặn ==")
		q = draft()
		code_q = as_qr(q, 10)
		_r, err = check_closing("A")
		blocked("5a QR 10 phút -> chặn", err, q)
		age(q, 16)
		_r, err = check_closing("A")
		passed("5b QR 16 phút -> không chặn", err)

		print("== 6. Job tự hủy (chỉ đơn thử) ==")
		pos121, pos30 = draft(), draft()
		age(pos121, 121)
		age(pos30, 30)
		q19 = draft()
		as_qr(q19, 19)
		age(q, 21)
		p2 = draft()
		as_user("A", P.pay_cash, p2)
		age(p2, 300)
		mine = {pos121, pos30, q, q19, p2}
		stale_pos = set(OC._stale_drafts(False, OC.POS_DRAFT_AUTO_CANCEL_MINUTES)) & mine
		stale_qr = set(OC._stale_drafts(True, OC.QR_PAY_WINDOW_MINUTES + OC.QR_CLEANUP_GRACE_MINUTES)) & mine
		ok("6a Job chọn Draft POS 121 phút, bỏ 30 phút, bỏ đơn QR và đơn Paid", stale_pos == {pos121}, f"({stale_pos})")
		ok("6b Job chọn QR 21 phút, bỏ QR 19 phút, bỏ Draft POS và đơn Paid", stale_qr == {q}, f"({stale_qr})")
		OC._cancel_batch(sorted(stale_pos), OC.reason_pos_stale(), OC.source_auto_pos())
		OC._cancel_batch(sorted(stale_qr), OC.REASON_QR_EXPIRED, OC.SOURCE_AUTO_QR)
		ok("6c POS 121 phút -> Cancelled, lý do 'Tự động (quá 2 giờ): Tự hủy quá 2 giờ'",
			is_cancelled(pos121, "Tự động (quá 2 giờ): Tự hủy quá 2 giờ"), f"({inv(pos121)})")
		ok("6d QR 21 phút -> Cancelled, lý do 'Tự động (QR hết hạn): …', giữ payment_code",
			is_cancelled(q, "Tự động (QR hết hạn): QR hết hạn không thanh toán") and inv(q).payment_code == code_q, f"({inv(q)})")
		ok("6d2 Chạy job lần nữa -> không chọn lại đơn đã hủy",
			not (set(OC._stale_drafts(True, 20)) | set(OC._stale_drafts(False, 120))) & {pos121, q})
		ok("6e Đơn Paid không bị đụng", frappe.db.get_value("POS Invoice", p2, "docstatus") == 1)
		cancel_paid(p2)

		print("== 7. Webhook ==")
		if not ctx["api_key"]:
			print("SKIP 7: Branch chưa có sepay_api_key")
		else:
			g = draft()
			code_g = as_qr(g, 18)
			amount_g = frappe.db.get_value("POS Invoice", g, "rounded_total") or frappe.db.get_value("POS Invoice", g, "grand_total")
			_r, err = webhook(code_g, amount_g, "ZZTEST-" + frappe.generate_hash(length=8))
			ok("7a QR 18 phút (trong đệm 5 phút) -> webhook thanh toán được",
				err is None and frappe.db.get_value("POS Invoice", g, "docstatus") == 1, f"({err})")
			cancel_paid(g)
			tid = "ZZTEST-" + frappe.generate_hash(length=8)
			res, err = webhook(code_q, 50000, tid)
			r1 = inv(q)
			ok("7b Webhook sau khi đơn đã hủy -> custom_late_payment = 1, mã giao dịch, đơn vẫn Cancelled",
				err is None and res and res.get("needs_review") and r1.custom_late_payment and tid in (r1.custom_late_payment_ref or "")
				and r1.docstatus == 2, f"({err or res})")
			ok("7b2 Giao dịch lưu trong sepay_payment_log + Comment 'Tiền về sau khi hủy'",
				tid in (r1.sepay_payment_log or "") and any("Tiền về sau khi hủy" in (c or "") for c in comments(q)))
			nl = frappe.get_all("Notification Log", filters={"document_type": "POS Invoice", "document_name": q, "for_user": users["M"]})
			ok("7c MANAGER của profile nhận Notification Log", bool(nl))
			n_comments = len(comments(q))
			_res, err = webhook(code_q, 50000, tid)
			r2 = inv(q)
			ok("7d Gọi lại cùng giao dịch -> không nhân đôi (ref, log, comment)",
				err is None and r2.custom_late_payment_ref == r1.custom_late_payment_ref
				and r2.sepay_payment_log == r1.sepay_payment_log and len(comments(q)) == n_comments, f"({r2.custom_late_payment_ref})")
			tid2 = "ZZTEST-" + frappe.generate_hash(length=8)
			_res, err = webhook(code_q, 50000, tid2)
			ok("7e Giao dịch thứ hai khác mã -> nối thêm mã", err is None and tid in (inv(q).custom_late_payment_ref or "")
				and tid2 in (inv(q).custom_late_payment_ref or ""))

		print("== 8. Thẻ bàn được nhả khi hủy ==")
		bz = [b for b in (as_user("A", P.get_buzzers)[0] or []) if b.get("available")]
		if not bz:
			print("SKIP 8: chi nhánh không có thẻ bàn đang trống")
		else:
			bname = bz[0]["name"]
			dd = draft("Dine In", buzzer=bname)
			held = [b for b in as_user("A", P.get_buzzers)[0] if b["name"] == bname][0]
			ok("8a Draft Dine In đang giữ thẻ", not held["available"] and held["used_by"] == dd)
			as_user("A", P.cancel_draft_order, dd, 0, "Khách đổi ý")
			free = [b for b in as_user("A", P.get_buzzers)[0] if b["name"] == bname][0]
			ok("8b Hủy đơn -> thẻ trống lại; đơn còn (Cancelled) và giữ mã thẻ",
				free["available"] and is_cancelled(dd, "Thủ công: Khách đổi ý") and frappe.db.get_value("POS Invoice", dd, "buzzer") == bname)

		print("== 9. Không còn đóng ca bắt buộc ==")
		ok("9a pos_api không còn force_close_shift / resolve_open_orders",
			not hasattr(P, "force_close_shift") and not hasattr(P, "resolve_open_orders"))
		ok("9b DocType MYPOS Order Cancel Log đã xóa", not frappe.db.exists("DocType", "MYPOS Order Cancel Log"))
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
				+ (frappe.get_all("POS Invoice", filters={"pos_profile": ctx["profile"]}, pluck="name") if ctx["profile"] else [])
			ok("10 Dọn dữ liệu: không còn profile / user / đơn thử trong DB", not left, f"({left})")
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
