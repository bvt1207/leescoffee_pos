# Self-test web đặt món QR — giai đoạn 1 (backend).
# Cách chạy: bench --site <site> console  -> dán TOÀN BỘ file này -> gọi:
#     run_order_qr_selftest()            # tự chọn POS Profile đang bật có branch + Price List
#     run_order_qr_selftest("Tên Branch")
#
# Điều kiện trước (script chỉ kiểm tra, không tự tạo):
#   - POS Profile đang bật có branch + selling_price_list; có MYPOS Menu cùng Price List, món có giá.
#   - Có POS Opening Entry đang Open của POS Profile đó (mở ca trên /pos hoặc Desk).
#   - Branch: sepay_enabled, sepay_va_account, sepay_bank_code, sepay_api_key đã điền.
#   - Có Mode of Payment loại Bank, có tài khoản mặc định cho Company.
# Script tự tạo mã QR, khách, đơn thử và tự dọn ở cuối (kể cả khi lỗi giữa chừng).
# KHÔNG đóng ca thật: phần "đóng ca" kiểm tra owner/pos_profile/get_pos_invoices của ca đang mở.


def run_order_qr_selftest(branch=None):
	import json
	import random
	import time
	import traceback

	import frappe
	from frappe.utils import add_to_date, flt, now_datetime
	from frappe.utils.password import get_decrypted_password
	from werkzeug.test import EnvironBuilder
	from werkzeug.wrappers import Request

	from leescoffee_pos.leescoffee_pos.api import customer_order_api as C
	from leescoffee_pos.leescoffee_pos.api import pos_api as P
	from leescoffee_pos.leescoffee_pos.doctype.mypos_order_qr.mypos_order_qr import get_qr_image
	from leescoffee_pos.leescoffee_pos.doctype.sepay import sepay as S

	admin = frappe.session.user
	results = []
	made = {"qr": [], "customers": [], "invoices": []}

	def check(label, ok, detail=""):
		results.append(bool(ok))
		print(("PASS " if ok else "FAIL ") + label + (f"  [{detail}]" if detail else ""))

	def guest(fn, *a, **kw):
		frappe.set_user("Guest")
		try:
			return fn(*a, **kw)
		finally:
			frappe.set_user(admin)

	def expect_error(label, fn, *a, contains=None, exc=Exception, **kw):
		try:
			guest(fn, *a, **kw)
		except exc as e:
			msg = str(e)
			check(label, contains is None or contains.lower() in msg.lower(), msg[:110])
		else:
			check(label, False, "không có lỗi")
		frappe.local.message_log = []

	def fake_request(payload, key=None):
		headers = {"Authorization": f"Apikey {key}"} if key else {}
		env = EnvironBuilder(
			method="POST",
			path="/api/method/leescoffee_pos.leescoffee_pos.doctype.sepay.sepay.sepay_webhook",
			json=payload,
			headers=headers,
		).get_environ()
		frappe.local.request = Request(env)
		frappe.local.request_ip = "127.0.0.1"

	def webhook_and_user():
		r = S.sepay_webhook()
		return r, frappe.session.user

	def rand_mobile():
		while True:
			m = "09" + "".join(random.choice("0123456789") for _x in range(8))
			if not frappe.db.exists("Customer", {"mobile_number": m}):
				return m

	frappe.cache.delete_keys("mypos_rl:")
	old_request = getattr(frappe.local, "request", None)
	try:
		# ---------------- 0. Điều kiện trước ----------------
		pf = {"disabled": 0, "branch": ["is", "set"], "selling_price_list": ["is", "set"]}
		if branch:
			pf["branch"] = branch
		pname = frappe.db.get_value("POS Profile", pf, "name")
		if not pname:
			print("DỪNG: không có POS Profile đang bật có branch + selling_price_list.")
			return
		profile = frappe.get_doc("POS Profile", pname)
		branch = profile.branch
		shift = C._open_shift(profile, throw=False)
		if not shift:
			print(f"DỪNG: POS Profile {pname} chưa có ca POS đang mở. Mở ca rồi chạy lại.")
			return
		# create_draft_order / pay_cash / cancel_draft_order chỉ cho POS CASHIER / POS MANAGER / System Manager /
		# Administrator (pos_api._require_sale_role, 2026-11-17). Người mở ca thiếu role -> bỏ qua 8k-8o.
		sale_ok = shift.user == "Administrator" or bool(
			set(frappe.get_roles(shift.user)) & {"POS CASHIER", "POS MANAGER", "System Manager"})

		class _SkipStaff(Exception):
			pass
		api_key = get_decrypted_password("Branch", branch, "sepay_api_key", raise_exception=False)
		try:
			C._require_sepay(branch)
			C._transfer_mode(profile)
		except Exception as e:
			print(f"DỪNG: cấu hình thanh toán chưa đủ: {e}")
			return
		print(f"Branch={branch} POS Profile={pname} ca={shift.name} (user {shift.user})\n")

		# ---------------- 1. Mã QR theo branch ----------------
		qr = frappe.get_doc({"doctype": "MYPOS Order QR", "branch": branch, "note": "selftest"}).insert()
		made["qr"].append(qr.name)
		check("1a Mã QR có token >= 24 ký tự", len(qr.token or "") >= 24, qr.token)
		check("1b order_url kết thúc bằng /order/<token>", (qr.order_url or "").endswith("/order/" + qr.token), qr.order_url)
		img = get_qr_image(qr.name)
		check("1c get_qr_image trả SVG (pyqrcode có sẵn)", bool(img.get("svg")), "có SVG" if img.get("svg") else "svg None -> chỉ có URL")
		qr_off = frappe.get_doc({"doctype": "MYPOS Order QR", "branch": branch, "enabled": 0}).insert()
		made["qr"].append(qr_off.name)
		check("1d get_shop với token hợp lệ", guest(C.get_shop, qr.token)["is_open"] is True)
		expect_error("1e get_shop với mã QR đã tắt bị chặn", C.get_shop, qr_off.token, contains="Mã QR")
		expect_error("1f get_shop với token bịa bị chặn", C.get_shop, "A" * 24, contains="Mã QR")

		# ---------------- 2. Đăng nhập khách mới / cũ ----------------
		mob_a, mob_b = rand_mobile(), rand_mobile()
		la = guest(C.login, qr.token, mob_a, "Khach Thu A")
		cust_a = frappe.db.get_value("Customer", {"mobile_number": mob_a}, "name")
		made["customers"].append(cust_a)
		check("2a Khách mới: tạo Customer theo SĐT", bool(cust_a and la.get("session_token")), cust_a)
		check("2b login không trả tên đã lưu / mã Customer", "customer" not in la and la["customer_name"] == "Khach Thu A")
		la2 = guest(C.login, qr.token, "+84" + mob_a[1:], "Ten Khac")
		n_same = frappe.db.count("Customer", {"mobile_number": mob_a})
		check("2c Khách cũ (+84...): không tạo trùng", n_same == 1, f"count={n_same}")
		check("2d Tên nhập khác: không ghi đè tên đã lưu",
			frappe.db.get_value("Customer", cust_a, "customer_name") == "Khach Thu A")
		lb = guest(C.login, qr.token, mob_b, "Khach Thu B")
		made["customers"].append(frappe.db.get_value("Customer", {"mobile_number": mob_b}, "name"))
		tok_a, tok_b = la["session_token"], lb["session_token"]
		expect_error("2e SĐT sai định dạng bị chặn", C.login, qr.token, "12345", "Ai Do", contains="Số điện thoại")
		expect_error("2f Đăng nhập bằng mã QR đã tắt bị chặn", C.login, qr_off.token, mob_a, "X Y", contains="Mã QR")

		# ---------------- 3. Token sai / hết hạn / thu hồi ----------------
		# Bọc riêng: lỗi ở đây được ghi FAIL, các mục sau vẫn chạy.
		try:
			bad = tok_a[:-2] + ("AA" if not tok_a.endswith("AA") else "BB")
			expect_error("3a Token bị sửa chữ ký -> chặn", C.get_me, bad, exc=frappe.PermissionError)
			expect_error("3b Token rác -> chặn", C.get_me, "abc", exc=frappe.PermissionError)

			# 3c: ký payload có exp trong quá khứ (không đi qua TTL cache). sid vẫn còn trong
			# cache (TTL dương) để chắc chắn bị chặn vì exp, không phải vì thu hồi.
			sid_exp = frappe.generate_hash(length=20)
			payload_exp = {"sid": sid_exp, "c": cust_a, "q": qr.name, "b": branch, "n": "Het Han",
				"exp": int(time.time()) - 60}
			body = C._b64(json.dumps(payload_exp, separators=(",", ":")).encode())
			tok_exp = f"{body}.{C._signature(body)}"
			frappe.cache.set_value(C._sid_key(sid_exp), cust_a, expires_in_sec=60)
			expect_error("3c Token hết hạn (exp quá khứ) -> chặn", C.get_me, tok_exp, exc=frappe.PermissionError)
			frappe.cache.delete_value(C._sid_key(sid_exp))

			# 3c2: TTL cấu hình sai (<= 0) -> _issue_session dùng mặc định, token vẫn dùng được.
			ttl_saved = C.SESSION_TTL_SECONDS
			C.SESSION_TTL_SECONDS = 0
			try:
				tok_ttl, exp_ttl = C._issue_session(cust_a, qr.name, branch, "TTL Mac Dinh")
			finally:
				C.SESSION_TTL_SECONDS = ttl_saved
			check("3c2 TTL <= 0 -> dùng mặc định, không lỗi Redis",
				exp_ttl > time.time() + 3600 and guest(C.get_me, tok_ttl)["customer_name"] == "TTL Mac Dinh")
			guest(C.logout, tok_ttl)

			tmp = guest(C.login, qr.token, mob_a, "Khach Thu A")["session_token"]
			guest(C.logout, tmp)
			expect_error("3d Token đã logout -> chặn", C.get_me, tmp, exc=frappe.PermissionError)
			frappe.db.set_value("MYPOS Order QR", qr.name, "enabled", 0)
			try:
				expect_error("3e Tắt mã QR -> phiên đang mở bị chặn", C.get_me, tok_a, exc=frappe.PermissionError)
			finally:
				frappe.db.set_value("MYPOS Order QR", qr.name, "enabled", 1)
			me = guest(C.get_me, tok_a)
			check("3f get_me: điểm/hạng, redeem_enabled = False", me["loyalty"].get("redeem_enabled") is False, str(me["loyalty"]))
		except Exception:
			check("3 Lỗi ngoài dự kiến ở mục token", False)
			traceback.print_exc()

		# ---------------- 4. Menu đúng branch + option_groups ----------------
		menu = guest(C.get_menu, tok_a)["menus"]
		items = [it for m in menu for it in m["items"]]
		check("4a Menu có món", bool(items), f"{len(menu)} menu, {len(items)} món")
		menus_pl = {r.name for r in frappe.get_all("MYPOS Menu", filters={"price_list": profile.selling_price_list}, fields=["name"])}
		check("4b Chỉ menu cùng Price List của POS Profile", {m["name"] for m in menu} <= menus_pl, profile.selling_price_list)
		check("4c Mỗi món có khóa option_groups", all("option_groups" in it for it in items))
		check("4d Không lộ price_list trong payload", all("price_list" not in m for m in menu))
		if not items:
			print("DỪNG: menu rỗng, không test tiếp được.")
			return

		it = items[0]
		code = it["sizes"][0]["item_code"]
		opts = []
		for g in it["option_groups"]:
			if g["required"]:
				dv = next((v["label"] for v in g["values"] if v["is_default"]), g["values"][0]["label"])
				opts.append({"group": g["name"], "value": dv})
		cart = [{"item_code": code, "qty": 2, "options": opts}]

		# ---------------- 5. Preview giá + CTKM ----------------
		pv = guest(C.preview, tok_a, cart)
		check("5a preview: grand_total > 0", flt(pv["grand_total"]) > 0, f"{pv['total_before']} -> {pv['grand_total']}")
		check("5b preview: có total_discount_rules, rules chỉ có title",
			"total_discount_rules" in pv and all(set(r) == {"title"} for x in pv["items"] for r in x["rules"]))
		expect_error("5c preview redeem_points > 0 bị từ chối", C.preview, tok_a, cart, redeem_points=5, contains="đổi điểm")
		expect_error("5d Món không có trong menu bị chặn", C.preview, tok_a,
			[{"item_code": "__KHONG_CO__", "qty": 1, "options": []}], contains="menu")
		expect_error("5e qty 99 bị chặn", C.preview, tok_a, [{"item_code": code, "qty": 99, "options": []}], contains="Số lượng")

		# ---------------- 6. Tạo đơn Take Away + Dine In ----------------
		expect_error("6a create_order redeem_points > 0 bị từ chối", C.create_order, tok_a, cart, "Take Away",
			redeem_points=3, contains="đổi điểm")
		ta = guest(C.create_order, tok_a, cart, "Take Away", order_note="<b>it da</b>")
		made["invoices"].append(ta["invoice_name"])
		di = guest(C.create_order, tok_a, cart, "Dine In")
		made["invoices"].append(di["invoice_name"])
		inv = frappe.db.get_value("POS Invoice", ta["invoice_name"],
			["order_channel", "guest_session", "qr_source", "buzzer", "docstatus", "owner", "order_note",
				"redeemed_points", "pos_profile", "grand_total"], as_dict=True)
		check("6b Take Away: Draft, kênh QR, có guest_session + qr_source",
			inv.docstatus == 0 and inv.order_channel == "QR" and inv.guest_session and inv.qr_source == qr.name)
		check("6c owner = user của ca POS (để đóng ca gom được)", inv.owner == shift.user, inv.owner)
		check("6d order_note đã bỏ thẻ HTML", inv.order_note == "it da", inv.order_note)
		check("6e Tổng đơn khớp preview", abs(flt(inv.grand_total) - flt(pv["grand_total"])) < 0.01)
		check("6f Dine In không gán thẻ rung",
			not frappe.db.get_value("POS Invoice", di["invoice_name"], "buzzer") and ta["stage"] == "awaiting_payment")
		expect_error("6g Đơn thứ 3 khi còn 2 đơn chờ thanh toán bị chặn", C.create_order, tok_a, cart, "Take Away",
			contains="chờ thanh toán")

		# ---------------- 7. Khách A / B tách biệt ----------------
		expect_error("7a Khách B không đọc được đơn của A", C.get_order, tok_b, ta["invoice_name"],
			exc=frappe.DoesNotExistError)
		expect_error("7b Khách B không sinh QR cho đơn của A", C.create_payment_qr, tok_b, ta["invoice_name"],
			exc=frappe.DoesNotExistError)
		check("7c get_my_orders của B rỗng", guest(C.get_my_orders, tok_b) == [])
		check("7d get_my_orders của A có 2 đơn", len(guest(C.get_my_orders, tok_a)) == 2)

		# ---------------- 8. QR thanh toán + webhook -> Paid -> Kitchen ----------------
		pay = guest(C.create_payment_qr, tok_a, ta["invoice_name"])
		check("8a create_payment_qr: có qr_url + payment_code", bool(pay["qr_url"] and pay["payment_code"]))
		pay2 = guest(C.create_payment_qr, tok_a, ta["invoice_name"])
		check("8b Gọi lại trả cùng payment_code", pay2["payment_code"] == pay["payment_code"])
		amount = flt(frappe.db.get_value("POS Invoice", ta["invoice_name"], "rounded_total")) or flt(inv.grand_total)
		payload = {"content": pay["payment_code"], "transferAmount": amount, "id": "SELFTEST-" + frappe.generate_hash(length=8),
			"transferType": "in", "gateway": "TEST"}
		fake_request(payload)
		expect_error("8c Webhook không có API key -> 403", S.sepay_webhook, exc=frappe.PermissionError)
		fake_request(payload, "sai-key")
		expect_error("8d Webhook sai API key -> 403", S.sepay_webhook, exc=frappe.PermissionError)
		check("8e Đơn vẫn Draft sau webhook giả", frappe.db.get_value("POS Invoice", ta["invoice_name"], "docstatus") == 0)
		fake_request(payload, api_key)
		res, user_after = guest(webhook_and_user)
		row = frappe.db.get_value("POS Invoice", ta["invoice_name"], ["docstatus", "status", "custom_kitchen_status"], as_dict=True)
		check("8f Webhook đúng key (Guest) -> Paid + Chưa làm", res.get("success") and row.docstatus == 1 and row.status == "Paid"
			and row.custom_kitchen_status == "Chưa làm", str(row))
		check("8f1 [HỒI QUY] Webhook LẦN ĐẦU cho đơn Draft không trả already_processed",
			"already_processed" not in res and res.get("docstatus") == 1, str(res)[:150])
		check("8f2 Sau webhook user trở lại Guest (quyền cao chỉ trong phạm vi save/submit)", user_after == "Guest", user_after)
		fake_request(payload, api_key)
		r8g = guest(S.sepay_webhook)
		check("8g Gửi lại webhook cùng giao dịch -> already_processed + invoice_name",
			r8g.get("already_processed") is True and r8g.get("invoice_name") == ta["invoice_name"], str(r8g))
		fake_request(dict(payload, content=pay["payment_code"].replace("-", "").lower()), api_key)
		r8g1 = guest(S.sepay_webhook)
		check("8g1 Retry với nội dung bị bỏ '-' / chữ thường (tra dự phòng) -> already_processed",
			r8g1.get("already_processed") is True, str(r8g1))
		review_title = "SePay: giao dịch cho đơn đã submit, cần đối soát"
		logs_before = frappe.db.count("Error Log", {"method": review_title})
		ref_before = frappe.db.get_value("POS Invoice", ta["invoice_name"], "transaction_ref")
		fake_request(dict(payload, id="SELFTEST-2ND-" + frappe.generate_hash(length=6)), api_key)
		r8g2 = guest(S.sepay_webhook)
		logs_after = frappe.db.count("Error Log", {"method": review_title})
		check("8g2 Giao dịch thứ hai cùng mã -> needs_review (không already_processed), không lộ đơn, có Error Log",
			r8g2.get("needs_review") is True and "invoice_name" not in r8g2 and "already_processed" not in r8g2
			and frappe.db.get_value("POS Invoice", ta["invoice_name"], "transaction_ref") == ref_before
			and logs_after == logs_before + 1, str(r8g2))
		fake_request(dict(payload, id="SELFTEST-X-" + frappe.generate_hash(length=6)), "sai-key")
		expect_error("8g3 Đơn đã thanh toán + sai key -> vẫn 403 (xác thực trước nhánh idempotent)",
			S.sepay_webhook, exc=frappe.PermissionError)
		frappe.local.request = old_request

		# 8k-8n: luồng máy POS cũ — đơn thu ngân tạo tại quầy, thu bằng QR SePay, webhook xác nhận.
		# [HỒI QUY] dùng LẠI id giao dịch của đơn TA (đã Paid) cho đơn Draft này: trước bản sửa,
		# nhánh 3c trả already_processed và KHÔNG thanh toán (lỗi LCNH-00279).
		try:
			if not sale_ok:
				raise _SkipStaff()
			frappe.set_user(shift.user)  # dùng ca đang mở của thu ngân, không mở ca mới
			try:
				staff = P.create_draft_order(cart, "Take Away", customer_name=cust_a,
					mode_of_payment=C._transfer_mode(profile)["name"], branch_name=branch,
					price_list=profile.selling_price_list)
				made["invoices"].append(staff["invoice_name"])
				sq = P.generate_qr(staff["invoice_name"])
			finally:
				frappe.set_user(admin)
			check("8k Đơn quầy (kênh POS) sinh QR", bool(sq.get("payment_code")) and
				frappe.db.get_value("POS Invoice", staff["invoice_name"], "order_channel") == "POS")
			s_amount = flt(staff["amount"])
			s_payload = {"content": sq["payment_code"], "transferAmount": s_amount,
				"id": payload["id"], "transferType": "in", "gateway": "TEST"}
			fake_request(s_payload, "sai-key")
			expect_error("8l Đơn quầy: webhook sai key -> 403", S.sepay_webhook, exc=frappe.PermissionError)
			fake_request(s_payload, api_key)
			s_res, s_user = guest(webhook_and_user)
			srow = frappe.db.get_value("POS Invoice", staff["invoice_name"],
				["docstatus", "status", "custom_kitchen_status", "payment_status"], as_dict=True)
			check("8m [HỒI QUY] Đơn quầy Draft + id từng dùng cho đơn khác -> vẫn Paid + Chưa làm + Đã thanh toán",
				s_res.get("success") and "already_processed" not in s_res and srow.docstatus == 1
				and srow.status == "Paid" and srow.custom_kitchen_status == "Chưa làm"
				and srow.payment_status == "Đã thanh toán" and s_user == "Guest", str(srow))
			fake_request(s_payload, api_key)
			check("8n Đơn quầy: SePay retry -> already_processed",
				guest(S.sepay_webhook).get("already_processed") is True)

			# 8o: đơn đã thu TIỀN MẶT (docstatus 1, payment_status khác "Đã thanh toán") rồi khách vẫn
			# chuyển khoản -> needs_review, không already_processed, không đổi đơn.
			frappe.set_user(shift.user)
			try:
				cash = P.create_draft_order(cart, "Take Away", customer_name=cust_a,
					mode_of_payment=C._transfer_mode(profile)["name"], branch_name=branch,
					price_list=profile.selling_price_list)
				made["invoices"].append(cash["invoice_name"])
				cq = P.generate_qr(cash["invoice_name"])
				P.pay_cash(cash["invoice_name"])
			finally:
				frappe.set_user(admin)
			fake_request({"content": cq["payment_code"], "transferAmount": flt(cash["amount"]),
				"id": "SELFTEST-CASH-" + frappe.generate_hash(length=6), "transferType": "in", "gateway": "TEST"}, api_key)
			r8o = guest(S.sepay_webhook)
			crow = frappe.db.get_value("POS Invoice", cash["invoice_name"], ["docstatus", "transaction_ref"], as_dict=True)
			check("8o Đơn đã thu tiền mặt + chuyển khoản -> needs_review, không already_processed, đơn không đổi",
				r8o.get("needs_review") is True and "already_processed" not in r8o
				and crow.docstatus == 1 and not crow.transaction_ref, str(r8o)[:150])
		except _SkipStaff:
			print(f"BỎ QUA 8k-8o: người mở ca {shift.user} chưa có POS CASHIER / POS MANAGER. "
				"Gán role cho user này (hoặc mở ca bằng thu ngân) rồi chạy lại.")
		except Exception:
			check("8k-8o Lỗi ngoài dự kiến ở luồng POS cũ", False)
			traceback.print_exc()
		frappe.local.request = old_request

		kitchen = P.get_kitchen_orders(status="Chưa làm")
		k = next((o for o in kitchen if o.name == ta["invoice_name"]), None)
		check("8h Kitchen thấy đơn QR (order_channel = QR)", bool(k and k.get("order_channel") == "QR"))
		P.set_kitchen_status(ta["invoice_name"], "Đã làm")
		st = guest(C.get_order, tok_a, ta["invoice_name"])
		check("8i Pha chế bấm Đã làm -> khách thấy stage ready", st["stage"] == "ready", st["stage_label"])
		P.set_kitchen_status(ta["invoice_name"], "Đã hoàn thành")
		try:
			P.confirm_pickup(ta["invoice_name"])
			check("8j confirm_pickup không lỗi khi không có thẻ rung", True)
		except Exception as e:
			check("8j confirm_pickup không lỗi khi không có thẻ rung", False, str(e))

		# ---------------- 9. Đóng ca: đơn QR thuộc ca đang mở ----------------
		# ERPNext mới: get_invoices(start, end, pos_profile, user) -> {"invoices": [...]}, lọc owner == user,
		# và chỉ gom POS Invoice khi POS Settings.invoice_type == "POS Invoice". Bản cũ: get_pos_invoices -> list.
		try:
			from erpnext.accounts.doctype.pos_closing_entry import pos_closing_entry as PCE

			inv_type = frappe.db.get_single_value("POS Settings", "invoice_type") if frappe.db.exists(
				"DocType", "POS Settings") else None
			check("9a POS Settings.invoice_type cho phép gom POS Invoice khi đóng ca",
				inv_type in (None, "", "POS Invoice"), f"invoice_type={inv_type!r}")

			opening = frappe.get_doc("POS Opening Entry", shift.name)
			fetch = getattr(PCE, "get_invoices", None) or getattr(PCE, "get_pos_invoices", None)
			if not fetch:
				check("9b Có hàm lấy đơn của ca (get_invoices/get_pos_invoices)", False, "ERPNext đổi API")
			else:
				got = fetch(opening.period_start_date, now_datetime(), profile.name, shift.user)
				rows = got.get("invoices", []) if isinstance(got, dict) else (got or [])
				names = {(r.get("pos_invoice") or r.get("name")) for r in rows}
				check(f"9b {fetch.__name__} của ca đang mở có đơn QR đã thanh toán", ta["invoice_name"] in names,
					f"{len(names)} đơn")
		except Exception as e:
			check("9b Lỗi khi kiểm tra đơn của ca", False, repr(e)[:150])

		# ---------------- 10. Hết hạn + dọn đơn ----------------
		frappe.db.set_value("POS Invoice", di["invoice_name"], "creation", add_to_date(now_datetime(), minutes=-20),
			update_modified=False)
		check("10a Quá 15 phút: stage expired", guest(C.get_order, tok_a, di["invoice_name"])["stage"] == "expired")
		expect_error("10b Quá 15 phút: không sinh QR", C.create_payment_qr, tok_a, di["invoice_name"], contains="hết hạn")
		pos_drafts = frappe.db.count("POS Invoice", {"docstatus": 0, "order_channel": "POS"})
		# Hạn 15 phút + đệm webhook 5 phút (order_cancel); quá mốc -> đơn chuyển Cancelled + lý do (2026-11-23, không xóa, không log riêng).
		frappe.db.set_value("POS Invoice", di["invoice_name"], "creation", add_to_date(now_datetime(), minutes=-19),
			update_modified=False)
		C.cleanup_expired_qr_orders()
		check("10c 19 phút: chưa hủy (đệm cho webhook trễ)",
			frappe.db.get_value("POS Invoice", di["invoice_name"], "docstatus") == 0)
		frappe.db.set_value("POS Invoice", di["invoice_name"], "creation", add_to_date(now_datetime(), minutes=-21),
			update_modified=False)
		C.cleanup_expired_qr_orders()
		row_di = frappe.db.get_value("POS Invoice", di["invoice_name"], ["docstatus", "status", "custom_cancel_reason"], as_dict=True)
		check("10d 21 phút: đơn Draft QR -> Cancelled, lý do 'Tự động (QR hết hạn): QR hết hạn không thanh toán'",
			row_di and row_di.docstatus == 2 and row_di.status == "Cancelled"
			and (row_di.custom_cancel_reason or "") == "Tự động (QR hết hạn): QR hết hạn không thanh toán", f"{row_di}")
		o_di = guest(C.get_order, tok_a, di["invoice_name"])
		check("10d2 Khách xem đơn đã hủy: stage expired, nhãn 'Đã hủy / hết hạn', không lỗi, không lộ lý do nội bộ",
			o_di["stage"] == "expired" and o_di["stage_label"] == "Đã hủy / hết hạn"
			and "QR hết hạn" not in frappe.as_json(o_di) and "cancel" not in frappe.as_json(o_di).lower(), f"{o_di.get('stage_label')}")
		expect_error("10d3 Đơn đã hủy: không sinh QR", C.create_payment_qr, tok_a, di["invoice_name"], contains="đã hủy")
		check("10e Đơn đã thanh toán không bị hủy", frappe.db.get_value("POS Invoice", ta["invoice_name"], "docstatus") == 1)
		check("10f Đơn Draft kênh POS không bị đụng",
			frappe.db.count("POS Invoice", {"docstatus": 0, "order_channel": "POS"}) == pos_drafts)

	except Exception:
		check("Lỗi ngoài dự kiến", False)
		traceback.print_exc()
	finally:
		frappe.local.request = old_request
		frappe.set_user(admin)
		# ---------------- Dọn dữ liệu thử ----------------
		for name in made["invoices"]:
			try:
				if not frappe.db.exists("POS Invoice", name):
					continue
				doc = frappe.get_doc("POS Invoice", name)
				if doc.docstatus == 1:
					doc.cancel()
				frappe.delete_doc("POS Invoice", name, force=True, ignore_permissions=True)
			except Exception as e:
				print(f"Chưa dọn được đơn {name}: {e}")
		for name in made["customers"]:
			try:
				if name and frappe.db.exists("Customer", name):
					frappe.delete_doc("Customer", name, force=True, ignore_permissions=True)
			except Exception as e:
				print(f"Chưa dọn được khách {name}: {e}")
		for name in made["qr"]:
			try:
				frappe.delete_doc("MYPOS Order QR", name, force=True, ignore_permissions=True)
			except Exception as e:
				print(f"Chưa dọn được mã QR {name}: {e}")
		frappe.cache.delete_keys("mypos_rl:")
		frappe.db.commit()
		print(f"\nTổng: {sum(results)}/{len(results)} PASS")
