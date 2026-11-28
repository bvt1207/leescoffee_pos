def check_sepay_hmac():
	"""Webhook SePay xác thực bằng HMAC-SHA256 (2026-11-28, docs/rules/sepay.md §1).

	    bench --site <site> execute mypos.selfcheck.sepay_hmac_check.check_sepay_hmac

	Dựng 1 quán thử ZZTEST-* (test_shop.py, Branch có sepay_webhook_secret, ca mở của Administrator), tạo đơn Draft + sinh QR,
	gọi sepay.sepay_webhook() dưới Guest với request giả (selfcheck/sepay_sign.py, ký đúng như SePay). Kiểm:
	  H1 thiếu header chữ ký / thiếu timestamp / timestamp không phải số -> 403, KHÔNG tìm đơn (không có Error Log "Not Found")
	  H2 ký bằng secret sai -> 403 "chữ ký sai", đơn vẫn Draft
	  H3 timestamp lệch +301 / -301 giây (ký đúng) -> 403 "timestamp quá hạn"
	  H4 payload bị sửa sau khi ký (đổi số tiền) -> 403 "chữ ký sai"
	  H5 không có chữ ký HMAC, chỉ có header Authorization hoặc tham số URL chứa secret -> 403 (không chấp nhận cách khác HMAC)
	  H6 raw body: make_form_dict (như Frappe làm với request thật) đọc body TRƯỚC, frappe.request.get_data() vẫn trả đúng bytes
	     đã ký -> chữ ký đúng được chấp nhận, đơn Paid
	  H7 phát lại đúng request đã xử lý thành công (sau commit) -> 403 "phát lại", đơn không đổi; request ký mới cùng giao dịch
	     -> already_processed
	  H8 request hợp lệ nhưng xử lý lỗi (sai số tiền) + rollback -> gửi lại đúng request đó KHÔNG bị coi là phát lại
	Dọn: drop quán thử; xóa khóa chống phát lại trong Redis của các chữ ký đã dùng.
	"""
	import json
	import time
	import traceback

	import frappe
	from frappe.utils import flt
	from frappe.utils.password import get_decrypted_password

	from mypos.mypos.api import pos_api as P
	from mypos.mypos.doctype.sepay import sepay as S
	from mypos.selfcheck.sepay_sign import next_timestamp, webhook_environ
	from mypos.selfcheck.test_shop import zz_test_shop

	results, used_sigs = [], []
	shop = None

	def ok(case, cond, extra=""):
		results.append((case, bool(cond)))
		print(f"{'PASS' if cond else 'FAIL'} {case} {extra}")

	def last_title():
		row = frappe.get_all("Error Log", filters={"method": ["like", "SePay%"]}, fields=["method"],
			order_by="creation desc", limit=1)
		return (row[0].method or "") if row else ""

	def not_found_count():
		return frappe.db.count("Error Log", {"method": "SePay POS Invoice Not Found"})

	def call(environ, form_dict_first=False):
		"""Gọi webhook dưới Guest với environ cho trước. Trả (kết quả, lỗi, request)."""
		from werkzeug.wrappers import Request

		old_req, old_fd = getattr(frappe.local, "request", None), frappe.local.form_dict
		req = Request(environ)
		frappe.local.request = req
		frappe.local.request_ip = "127.0.0.1"
		sig = req.headers.get(S.SIGNATURE_HEADER)
		if sig:
			used_sigs.append(sig.strip().lower())
		try:
			if form_dict_first:
				from frappe.app import make_form_dict

				make_form_dict(req)
			frappe.set_user("Guest")
			return S.sepay_webhook(), None, req
		except Exception as e:  # noqa: BLE001
			frappe.clear_messages()
			return None, e, req
		finally:
			frappe.set_user("Administrator")
			frappe.local.request = old_req
			frappe.local.form_dict = old_fd

	def denied(case, err, title_part=None):
		cond = isinstance(err, frappe.PermissionError) and (title_part is None or title_part in last_title())
		ok(case, cond, f"-> {type(err).__name__ if err else 'KHÔNG lỗi'} / log: {last_title()}")

	def status(name):
		return frappe.db.get_value("POS Invoice", name, ["docstatus", "status", "payment_status", "transaction_ref", "modified"],
			as_dict=True)

	def body_of(payload):
		return json.dumps(payload, ensure_ascii=False).encode("utf-8")

	frappe.set_user("Administrator")
	try:
		shop = zz_test_shop("create", quiet=True)
		if not shop.get("ok"):
			print(f"SKIP: {shop.get('reason')}")
			print("KẾT QUẢ: SKIP")
			shop = None
			return None
		secret = get_decrypted_password("Branch", shop["branch"], "sepay_webhook_secret", raise_exception=False)
		if not secret:
			ok("H0 quán thử có sepay_webhook_secret", False, "(test_shop chưa đặt secret)")
			raise RuntimeError("thiếu secret")

		def qr_draft():
			res = P.create_draft_order([{"item_code": shop["item"], "qty": 1}], "Take Away", branch_name=shop["branch"],
				price_list=shop["price_list"])
			inv = res["invoice_name"]
			code = P.generate_qr(inv)["payment_code"]
			r = frappe.db.get_value("POS Invoice", inv, ["rounded_total", "grand_total"], as_dict=True)
			return inv, code, flt(r.rounded_total or r.grand_total)

		inv, code, amount = qr_draft()
		frappe.db.commit()
		tid = "ZZTEST-HMAC-" + frappe.generate_hash(length=8)
		payload = {"content": code, "transferAmount": amount, "id": tid, "transferType": "in", "gateway": "TEST"}
		body = body_of(payload)

		print("== H1. Thiếu header ==")
		nf = not_found_count()
		_r, e, _q = call(webhook_environ(body=body))
		denied("H1a Không có header chữ ký nào -> 403", e, "thiếu chữ ký HMAC")
		_r, e, _q = call(webhook_environ(body=body, headers={S.SIGNATURE_HEADER: S.sepay_signature(secret, next_timestamp(), body)}))
		denied("H1b Có chữ ký, thiếu timestamp -> 403", e, "thiếu chữ ký HMAC")
		_r, e, _q = call(webhook_environ(body=body, secret=secret, timestamp="abc"))
		denied("H1c Timestamp không phải số -> 403", e, "timestamp không hợp lệ")
		ok("H1d Không tìm đơn khi thiếu chữ ký (không thêm Error Log Not Found)", not_found_count() == nf)

		print("== H2. Secret sai ==")
		_r, e, _q = call(webhook_environ(body=body, secret="wrong-" + secret))
		denied("H2a Ký bằng secret sai -> 403", e, "chữ ký sai")
		ok("H2b Đơn vẫn Draft", status(inv).docstatus == 0, f"({status(inv)})")

		print("== H3. Timestamp lệch ==")
		now_ts = int(time.time())
		for case, ts in (("H3a +301 giây", now_ts + 301 + 5), ("H3b -301 giây", now_ts - 301 - 5)):
			_r, e, _q = call(webhook_environ(body=body, secret=secret, timestamp=str(ts)))
			denied(f"{case} (ký đúng) -> 403", e, "timestamp quá hạn")

		print("== H4. Payload bị sửa ==")
		ts = next_timestamp()
		sig_a = S.sepay_signature(secret, ts, body)
		tampered = body_of(dict(payload, transferAmount=amount + 1000))
		_r, e, _q = call(webhook_environ(body=tampered, secret=secret, timestamp=ts, signature=sig_a))
		denied("H4 Đổi số tiền sau khi ký -> 403", e, "chữ ký sai")

		print("== H5. Cách xác thực cũ ==")
		_r, e, _q = call(webhook_environ(body=body, headers={"Authorization": f"Bearer {secret}"}))
		denied("H5a Header Authorization chứa secret -> 403", e, "thiếu chữ ký HMAC")
		_r, e, _q = call(webhook_environ(body=body, query_string={"key": secret}))
		denied("H5b Tham số URL chứa secret -> 403", e, "thiếu chữ ký HMAC")
		ok("H5c Đơn vẫn Draft sau mọi request bị từ chối", status(inv).docstatus == 0, f"({status(inv)})")

		print("== H6. Raw body sau make_form_dict + chữ ký đúng ==")
		good_env = webhook_environ(body=body, secret=secret)
		res, e, req = call(dict(good_env), form_dict_first=True)
		ok("H6a get_data() sau make_form_dict = đúng bytes đã ký", req.get_data() == body, f"({len(req.get_data())} / {len(body)} bytes)")
		st = status(inv)
		ok("H6b Chữ ký đúng -> chấp nhận, đơn Paid + Đã thanh toán", e is None and res and res.get("success")
			and st.docstatus == 1 and st.status == "Paid" and st.transaction_ref == tid, f"({e or st})")
		frappe.db.commit()  # after_commit -> nhớ chữ ký

		print("== H7. Phát lại ==")
		before = status(inv).modified
		_r, e, _q = call(dict(good_env))
		denied("H7a Gửi lại đúng request đã xử lý -> 403 phát lại", e, "phát lại")
		ok("H7b Đơn không đổi", status(inv).modified == before)
		res, e, _q = call(webhook_environ(body=body, secret=secret))
		ok("H7c Request ký mới cùng giao dịch -> already_processed", e is None and res and res.get("already_processed") is True,
			f"({e or res})")

		print("== H8. Lỗi xử lý + rollback -> gửi lại không bị coi là phát lại ==")
		inv2, code2, amount2 = qr_draft()
		frappe.db.commit()
		bad_env = webhook_environ({"content": code2, "transferAmount": amount2 + 1, "id": tid + "-2", "transferType": "in",
			"gateway": "TEST"}, secret)
		_r, e1, _q = call(dict(bad_env))
		frappe.db.rollback()
		_r, e2, _q = call(dict(bad_env))
		frappe.db.rollback()
		ok("H8a Lần 1 lỗi sai số tiền (không phải 403)", e1 is not None and not isinstance(e1, frappe.PermissionError),
			f"({type(e1).__name__ if e1 else 'KHÔNG lỗi'})")
		ok("H8b Gửi lại sau rollback -> vẫn xử lý (lỗi số tiền), không bị 403 phát lại",
			e2 is not None and not isinstance(e2, frappe.PermissionError), f"({type(e2).__name__ if e2 else 'KHÔNG lỗi'}: {str(e2)[:80]})")
		ok("H8c Đơn 2 vẫn Draft", status(inv2).docstatus == 0)
	except Exception:  # noqa: BLE001
		ok("Lỗi ngoài dự kiến", False)
		traceback.print_exc()
	finally:
		frappe.set_user("Administrator")
		try:
			frappe.db.rollback()
		except Exception:  # noqa: BLE001
			pass
		for sig in set(used_sigs):
			try:
				frappe.cache.delete_value(S._replay_key(sig))
			except Exception:  # noqa: BLE001
				pass
		if shop:
			zz_test_shop("drop", shop["tag"], quiet=True)

	fails = [c for c, r in results if not r]
	print(f"KẾT QUẢ: {'PASS' if not fails else 'FAIL'} ({len(results) - len(fails)}/{len(results)})"
		+ (f" — lỗi: {', '.join(fails)}" if fails else ""))
	return {"ok": not fails, "results": results}
