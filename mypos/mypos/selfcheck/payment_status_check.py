def check_payment_status(pos_profile=None, item_code=None, mode_of_payment=None, price_list=None):
	"""POS Invoice.payment_status ("Trạng thái thanh toán") tính ở MỘT nơi (2026-11-25).

	Dán CẢ hàm vào `bench --site <site> console` MỚI (SAU khi migrate) rồi gọi, ví dụ:
	    check_payment_status("<POS Profile>", "<mã món VARIANT>", "Cash", price_list="<Price List của MYPOS Menu>")

	Quy tắc: nháp "Chưa thanh toán"; sinh QR "Đang chờ"; submit (không phải trả hàng) "Đã thanh toán" (hook before_submit);
	hủy (nháp hoặc đã submit) "Hủy"; đơn trả hàng hook không đụng.
	KHÔNG đụng ca / đơn thật: chép POS Profile thành "ZZTEST Pay ...", user tạm A (POS CASHIER), Customer khách vãng lai tạm.
	Webhook mô phỏng bằng request giả, cần Branch có sepay_api_key + VA + mã NH (thiếu -> SKIP các ca 3, 6).
	Có commit -> cuối hàm dọn mọi dữ liệu thử (commit trước mỗi lần xóa, thử lại 3 lần khi QueryDeadlockError); lỗi dọn chỉ in WARN; dòng KẾT QUẢ luôn in.
	Đơn QR khách tự đặt (/order): kiểm bằng run_order_qr_selftest() (8m, 8n, 8o) + run_order_history_selftest().
	"""
	if pos_profile is None:  # không truyền dữ liệu -> tự dựng quán thử tạm (selfcheck/test_shop.py), dọn ở cuối
		from mypos.selfcheck.test_shop import zz_test_shop

		_shop = zz_test_shop("create", open_shift=False)
		if not _shop.get("ok"):
			print(f"SKIP: {_shop.get('reason')}")
			print("KẾT QUẢ: SKIP")
			return None
		try:
			return check_payment_status(_shop["pos_profile"], _shop["item"], _shop["mop_cash"], _shop["price_list"])
		finally:
			zz_test_shop("drop", _shop["tag"])

	import json
	import time
	import traceback

	import frappe
	from frappe.utils import flt, now_datetime, nowdate
	from frappe.utils.password import get_decrypted_password
	from werkzeug.test import EnvironBuilder
	from werkzeug.wrappers import Request

	from mypos.mypos.api import pos_api as P
	from mypos.mypos.doctype.pos_invoice_hooks import order_cancel as OC
	from mypos.mypos.doctype.pos_invoice_hooks import pos_invoice_hooks as PH
	from mypos.mypos.doctype.sepay import sepay as S

	PREFIX = "zz.test.pay"
	PROFILE_PREFIX = "ZZTEST Pay "
	WALK_IN_PREFIX = "ZZTEST WI Pay "
	UNPAID, WAITING, PAID, CANCELLED = PH.PAYMENT_UNPAID, PH.PAYMENT_WAITING, PH.PAYMENT_PAID, PH.PAYMENT_CANCELLED
	DEADLOCK = getattr(frappe, "QueryDeadlockError", None) or getattr(frappe.exceptions, "QueryDeadlockError", ())
	results, users, ctx = [], {}, {"profile": None}

	def ok(case, cond, extra=""):
		results.append((case, bool(cond)))
		print(f"{'PASS' if cond else 'FAIL'} {case} {extra}")

	def skip(case, why):
		print(f"SKIP {case} ({why})")

	def as_user(key, fn, *args, **kw):
		frappe.set_user(users[key])
		try:
			return fn(*args, **kw), None
		except Exception as e:  # noqa: BLE001
			frappe.clear_messages()
			return None, e
		finally:
			frappe.set_user("Administrator")

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
				invs = frappe.get_all("POS Invoice", filters={"pos_profile": prof}, fields=["name", "is_return"])
				for inv in invs:
					for nl in frappe.get_all("Notification Log", filters={"document_type": "POS Invoice", "document_name": inv.name}, pluck="name"):
						delete_fresh("Notification Log", nl, removed, failed)
				# Đơn trả hàng trước (đơn gốc không hủy được khi còn đơn trả đang submit).
				for inv in sorted(invs, key=lambda r: -int(r.is_return or 0)):
					delete_fresh("POS Invoice", inv.name, removed, failed, cancel=True)
				for dt in ("POS Closing Entry", "POS Opening Entry"):
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
	def draft():
		line = [{"item_code": item_code, "qty": 1, "options": []}]
		res, err = as_user("A", P.create_draft_order, line, "Take Away", mode_of_payment=mode_of_payment,
			price_list=ctx["price_list"])
		if err:
			raise err
		return res["invoice_name"]

	def row(name):
		return frappe.db.get_value("POS Invoice", name, ["docstatus", "status", "payment_status", "transaction_ref",
			"custom_late_payment", "modified", "is_return"], as_dict=True)

	def amount_of(name):
		r = frappe.db.get_value("POS Invoice", name, ["rounded_total", "grand_total"], as_dict=True)
		return flt(r.rounded_total or r.grand_total)

	def webhook(code, amount, tid):
		env = EnvironBuilder(method="POST", path="/api/method/mypos.mypos.doctype.sepay.sepay.sepay_webhook",
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

	def version_has_paid(name):
		for data in frappe.get_all("Version", filters={"ref_doctype": "POS Invoice", "docname": name}, pluck="data"):
			try:
				changed = json.loads(data or "{}").get("changed") or []
			except Exception:  # noqa: BLE001
				continue
			if any(c[0] == "payment_status" and c[2] == PAID for c in changed if len(c) >= 3):
				return True
		return False

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
		wi = frappe.new_doc("Customer")
		wi.customer_name = f"{WALK_IN_PREFIX}{frappe.generate_hash(length=6)}"
		wi.customer_type = "Individual"
		wi.customer_group = frappe.db.get_single_value("Selling Settings", "customer_group") or "Individual"
		wi.territory = frappe.db.get_single_value("Selling Settings", "territory") or "All Territories"
		wi.insert(ignore_permissions=True)
		ctx["price_list"] = price_list or src.get("selling_price_list")
		modes = [p.mode_of_payment for p in (src.get("payments") or []) if p.mode_of_payment] or [mode_of_payment]
		email = f"{PREFIX}.a@example.com"
		frappe.get_doc({"doctype": "User", "email": email, "first_name": "ZZTEST A", "user_type": "System User",
			"send_welcome_email": 0, "enabled": 1, "roles": [{"role": "POS CASHIER"}]}).insert(ignore_permissions=True)
		users["A"] = email
		prof = frappe.copy_doc(src)
		prof.set("__newname", f"{PROFILE_PREFIX}{frappe.generate_hash(length=6)}")
		prof.set("custom_walk_in_customer", wi.name)
		prof.disabled = 0
		prof.set("applicable_for_users", [{"user": users["A"], "default": 0}])
		# Mỗi Branch tối đa 1 profile đang bật (pos_profile_hooks): cờ chỉ dùng cho self-test.
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
		branch = prof.get("branch")
		ctx["api_key"] = get_decrypted_password("Branch", branch, "sepay_api_key", raise_exception=False) if branch else None
		print(f"INFO profile {prof.name}, ca {ctx['shift']}, branch {branch}, webhook {'có key' if ctx['api_key'] else 'SKIP'}")

		print("== 2. Thu tiền mặt / submit tay ==")
		d = draft()
		ok("2a Đơn nháp mới -> Chưa thanh toán", row(d).payment_status == UNPAID, f"({row(d).payment_status})")
		_r, err = as_user("A", P.pay_cash, d)
		r = row(d)
		ok("2b pay_cash -> Paid + Đã thanh toán ngay sau submit", err is None and r.docstatus == 1 and r.status == "Paid"
			and r.payment_status == PAID, f"({err or r})")
		ok("2c Version của lần submit ghi payment_status -> Đã thanh toán", version_has_paid(d))
		d2 = draft()
		doc = frappe.get_doc("POS Invoice", d2)
		for p in doc.payments:
			p.amount = amount_of(d2)
		doc.flags.ignore_permissions = True
		doc.save()
		doc.submit()
		r = row(d2)
		ok("2d Submit tay (không qua pos_api) -> Đã thanh toán", r.docstatus == 1 and r.payment_status == PAID, f"({r})")

		print("== 3. Sinh QR -> Đang chờ; hủy cần xác nhận ==")
		dq = draft()
		qr, err = as_user("A", P.generate_qr, dq)
		if err:
			skip("3a-3d", f"generate_qr lỗi (Branch chưa cấu hình SePay?): {str(err)[:100]}")
		else:
			ok("3a generate_qr -> Đang chờ (trả về + DB)", qr.get("payment_status") == WAITING and row(dq).payment_status == WAITING,
				f"({qr.get('payment_status')} / {row(dq).payment_status})")
			qr2, _e = as_user("A", P.generate_qr, dq)
			ok("3b Gọi lại generate_qr (idempotent) -> cùng mã, vẫn Đang chờ",
				qr2 and qr2.get("payment_code") == qr.get("payment_code") and qr2.get("payment_status") == WAITING)
			_r, err = as_user("A", P.cancel_draft_order, dq, 0, "Khách đổi ý")
			ok("3c Hủy đơn Đang chờ không force -> chặn (đang chờ thanh toán)", err is not None and "đang chờ thanh toán" in str(err),
				f"-> {str(err)[:100]}" if err else "-> KHÔNG chặn")
			_r, err = as_user("A", P.cancel_draft_order, dq, 1, "Khách đổi ý")
			r = row(dq)
			ok("3d Hủy có force=1 -> Cancelled + Hủy", err is None and r.docstatus == 2 and r.payment_status == CANCELLED, f"({err or r})")
			ctx["qr_cancelled"] = (dq, qr.get("payment_code"))

		print("== 4. Hủy đơn nháp (không QR) / hủy đơn đã submit ==")
		dc = draft()
		_r, err = as_user("A", P.cancel_draft_order, dc, 0, "Đặt nhầm")
		r = row(dc)
		ok("4a cancel_draft_order -> Cancelled + Hủy", err is None and r.docstatus == 2 and r.payment_status == CANCELLED, f"({err or r})")
		dj = draft()
		OC.cancel_draft(dj, "Tự hủy quá 2 giờ", OC.source_auto_pos())
		ok("4b order_cancel.cancel_draft (đường job tự hủy) -> Hủy", row(dj).payment_status == CANCELLED, f"({row(dj).payment_status})")
		doc = frappe.get_doc("POS Invoice", d2)
		doc.flags.ignore_permissions = True
		try:
			doc.cancel()
			r = row(d2)
			ok("4c Hủy đơn đã submit (on_cancel) -> Hủy", r.docstatus == 2 and r.payment_status == CANCELLED, f"({r})")
		except Exception as e:  # noqa: BLE001
			frappe.clear_messages()
			skip("4c", f"ERPNext không cho hủy đơn: {str(e)[:100]}")

		print("== 5. Đơn trả hàng: hook không đụng ==")
		try:
			from erpnext.accounts.doctype.pos_invoice.pos_invoice import make_sales_return

			ret = make_sales_return(d)
			ret.flags.ignore_permissions = True
			ret.payment_status = UNPAID  # giá trị đánh dấu: hook không được đổi
			ret.insert()
			ret.submit()
			r = row(ret.name)
			ok("5a Đơn trả hàng submit -> payment_status giữ nguyên (không thành Đã thanh toán)",
				r.is_return and r.docstatus == 1 and r.payment_status == UNPAID, f"({r})")
			ctx["return"] = ret.name
		except Exception as e:  # noqa: BLE001
			frappe.clear_messages()
			skip("5a", f"không tạo được đơn trả hàng: {str(e)[:120]}")

		print("== 6. Webhook SePay (bỏ dòng gán ở webhook, hook before_submit ghi) ==")
		if not ctx["api_key"]:
			skip("6a-6e", "Branch chưa có sepay_api_key")
		else:
			dw = draft()
			qw, err = as_user("A", P.generate_qr, dw)
			if err:
				skip("6a-6e", f"generate_qr lỗi: {str(err)[:100]}")
			else:
				tid = "ZZTEST-PAY-" + frappe.generate_hash(length=8)
				res, err = webhook(qw["payment_code"], amount_of(dw), tid)
				r = row(dw)
				ok("6a Webhook -> submit, Paid, Đã thanh toán, transaction_ref đúng", err is None and r.docstatus == 1
					and r.status == "Paid" and r.payment_status == PAID and r.transaction_ref == tid, f"({err or r})")
				before = r.modified
				res2, err = webhook(qw["payment_code"], amount_of(dw), tid)
				ok("6b Gọi lại cùng giao dịch -> already_processed, đơn không đổi",
					err is None and res2 and res2.get("already_processed") is True and row(dw).modified == before, f"({err or res2})")
				res3, err = webhook(qw["payment_code"], amount_of(dw), tid + "-X")
				ok("6c Giao dịch khác cùng mã (đơn đã submit) -> needs_review, không already_processed",
					err is None and res3 and res3.get("needs_review") and not res3.get("already_processed"), f"({err or res3})")
				if ctx.get("qr_cancelled"):
					name_c, code_c = ctx["qr_cancelled"]
					res4, err = webhook(code_c, amount_of(name_c), "ZZTEST-LATE-" + frappe.generate_hash(length=6))
					r = row(name_c)
					ok("6d Tiền về đơn đã hủy -> needs_review, đơn vẫn Cancelled + Hủy, có cờ tiền về sau hủy",
						err is None and res4 and res4.get("needs_review") and r.docstatus == 2 and r.payment_status == CANCELLED
						and r.custom_late_payment, f"({err or res4} / {r})")
				else:
					skip("6d", "không có đơn QR đã hủy từ ca 3")
				_res5, err = webhook("ZZTEST-KHONG-CO-" + frappe.generate_hash(length=6), 1000, "ZZTEST-ORPHAN")
				ok("6e Giao dịch mồ côi (không khớp đơn) -> lỗi, không đơn nào bị đổi", err is not None, f"({err})")

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
		except Exception:  # noqa: BLE001
			print("WARN dọn dữ liệu lỗi:")
			traceback.print_exc()
		frappe.set_user(admin)
		passed = sum(1 for _c, r in results if r)
		print(f"KẾT QUẢ: {passed}/{len(results)} PASS")
