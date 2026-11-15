# Self-test "Đơn của tôi" lưu theo khách (get_my_orders theo Customer + chi nhánh, không theo sid),
# cart_key, giới hạn tần suất, hồi quy webhook SePay.
# Cách chạy: bench --site <site> console -> dán file order_qr_selftest.py RỒI dán file này -> gọi:
#     run_order_history_selftest()             # chạy bộ mới, xong tự gọi run_order_qr_selftest() (bộ cũ)
#     run_order_history_selftest(run_old=False)
#     run_order_history_selftest("Tên Branch")
#
# Điều kiện trước: giống order_qr_selftest.py (POS Profile có branch + Price List, ca POS đang mở,
# Branch đủ cấu hình SePay + API key, Mode of Payment loại Bank).
# Script tự tạo mã QR, Branch tạm, khách, đơn thử và tự dọn ở cuối (kể cả khi lỗi giữa chừng).


def run_order_history_selftest(branch=None, run_old=True):
	import json
	import random
	import traceback

	import frappe
	from frappe.utils import add_to_date, flt, now_datetime
	from frappe.utils.password import get_decrypted_password
	from werkzeug.test import EnvironBuilder
	from werkzeug.wrappers import Request

	from leescoffee_pos.leescoffee_pos.api import customer_order_api as C
	from leescoffee_pos.leescoffee_pos.doctype.sepay import sepay as S

	admin = frappe.session.user
	results = []
	made = {"qr": [], "customers": [], "invoices": [], "branches": []}

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

	def rand_mobile():
		while True:
			m = "09" + "".join(random.choice("0123456789") for _x in range(8))
			if not frappe.db.exists("Customer", {"mobile_number": m}):
				return m

	def names(lst):
		return {o["invoice_name"]: o.get("group") for o in lst}

	def set_inv(name, **values):
		frappe.db.set_value("POS Invoice", name, values, update_modified=False)

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
		api_key = get_decrypted_password("Branch", branch, "sepay_api_key", raise_exception=False)
		try:
			C._require_sepay(branch)
			C._transfer_mode(profile)
		except Exception as e:
			print(f"DỪNG: cấu hình thanh toán chưa đủ: {e}")
			return
		print(f"Branch={branch} POS Profile={pname} ca={shift.name}\n")

		qr = frappe.get_doc({"doctype": "MYPOS Order QR", "branch": branch, "note": "selftest-history"}).insert()
		made["qr"].append(qr.name)
		mob_a, mob_b = rand_mobile(), rand_mobile()
		la = guest(C.login, qr.token, mob_a, "Lich Su A")
		cust_a = frappe.db.get_value("Customer", {"mobile_number": mob_a}, "name")
		made["customers"].append(cust_a)
		lb = guest(C.login, qr.token, mob_b, "Lich Su B")
		cust_b = frappe.db.get_value("Customer", {"mobile_number": mob_b}, "name")
		made["customers"].append(cust_b)
		tok_a, tok_b = la["session_token"], lb["session_token"]

		# ---------------- H0. cart_key ----------------
		check("H0a login trả cart_key, không chứa mã Customer/SĐT",
			bool(la.get("cart_key")) and cust_a not in la["cart_key"] and mob_a not in la["cart_key"])
		check("H0b cart_key khác nhau giữa A và B", la["cart_key"] != lb["cart_key"])
		check("H0c get_me trả cùng cart_key", guest(C.get_me, tok_a).get("cart_key") == la["cart_key"])

		menu = guest(C.get_menu, tok_a)["menus"]
		items = [it for m in menu for it in m["items"]]
		if not items:
			print("DỪNG: menu rỗng.")
			return
		it = items[0]
		opts = []
		for g in it["option_groups"]:
			if g["required"]:
				dv = next((v["label"] for v in g["values"] if v["is_default"]), g["values"][0]["label"])
				opts.append({"group": g["name"], "value": dv})
		cart = [{"item_code": it["sizes"][0]["item_code"], "qty": 1, "options": opts}]

		# ---------------- H1. Đơn 1 của A: thanh toán qua webhook (hồi quy SePay) ----------------
		o1 = guest(C.create_order, tok_a, cart, "Take Away")["invoice_name"]
		made["invoices"].append(o1)
		pay = guest(C.create_payment_qr, tok_a, o1)
		amount = flt(frappe.db.get_value("POS Invoice", o1, "rounded_total")) or flt(
			frappe.db.get_value("POS Invoice", o1, "grand_total"))
		payload = {"content": pay["payment_code"], "transferAmount": amount,
			"id": "SELFTEST-H-" + frappe.generate_hash(length=8), "transferType": "in", "gateway": "TEST"}
		fake_request(payload, api_key)
		r1 = guest(S.sepay_webhook)
		row = frappe.db.get_value("POS Invoice", o1, ["docstatus", "status", "payment_status"], as_dict=True)
		check("H1a [HỒI QUY SePay] Draft thanh toán lần đầu -> Paid, không already_processed",
			r1.get("success") and "already_processed" not in r1 and row.docstatus == 1 and row.status == "Paid"
			and row.payment_status == "Đã thanh toán", str(r1)[:150])
		fake_request(payload, api_key)
		r2 = guest(S.sepay_webhook)
		check("H1b [HỒI QUY SePay] Gửi lại cùng giao dịch -> already_processed + invoice_name",
			r2.get("already_processed") is True and r2.get("invoice_name") == o1, str(r2)[:150])
		frappe.local.request = old_request

		# Đơn 2 của A: còn chờ thanh toán (có payment_code)
		o2 = guest(C.create_order, tok_a, cart, "Dine In")["invoice_name"]
		made["invoices"].append(o2)
		guest(C.create_payment_qr, tok_a, o2)
		o2_code = frappe.db.get_value("POS Invoice", o2, "payment_code")

		# ---------------- H2. Cùng phiên ----------------
		g = names(guest(C.get_my_orders, tok_a))
		check("H2a Cùng phiên: đơn đã trả (active) + đơn chờ thanh toán (active)",
			g.get(o1) == "active" and g.get(o2) == "active", str(g))

		# ---------------- H3. Đăng xuất + đăng nhập lại ----------------
		guest(C.logout, tok_a)
		expect_error("H3a Token cũ sau đăng xuất bị chặn", C.get_my_orders, tok_a, exc=frappe.PermissionError)
		tok_a2 = guest(C.login, qr.token, mob_a, "Lich Su A")["session_token"]
		lst = guest(C.get_my_orders, tok_a2)
		g = names(lst)
		check("H3b Đăng nhập lại: vẫn thấy đơn đã thanh toán", o1 in g, str(g))
		check("H3c Đơn chờ thanh toán của phiên cũ KHÔNG hiện ở phiên mới", o2 not in g, str(g))
		expect_error("H3d Phiên mới không đọc get_order đơn chờ thanh toán của phiên cũ", C.get_order, tok_a2, o2,
			exc=frappe.DoesNotExistError)

		# ---------------- H4. Dữ liệu tối thiểu ----------------
		dump = json.dumps(lst, ensure_ascii=False, default=str)
		check("H4a Không chứa SĐT, mã Customer, payment_code",
			mob_a not in dump and mob_a[1:] not in dump and cust_a not in dump
			and pay["payment_code"] not in dump and (o2_code or "§") not in dump)
		bad_keys = {"payment_code", "mobile", "mobile_number", "customer", "transaction_ref", "sepay_payment_log",
			"loyalty", "loyalty_points"}
		check("H4b Không có khóa nhạy cảm, ghi chú rỗng",
			all(not (bad_keys & set(o)) and o["order_note"] == "" for o in lst), str(lst[0].keys()) if lst else "")

		# ---------------- H5. Khách B ----------------
		check("H5a Khách B không thấy đơn của A", guest(C.get_my_orders, tok_b) == [])
		expect_error("H5b Khách B không get_order được đơn của A", C.get_order, tok_b, o1, exc=frappe.DoesNotExistError)

		# ---------------- H6. Active -> Lịch sử ----------------
		set_inv(o1, custom_kitchen_status="Đã hoàn thành")
		check("H6a Đã hoàn thành -> history", names(guest(C.get_my_orders, tok_a2)).get(o1) == "history")
		creation_o1 = frappe.db.get_value("POS Invoice", o1, "creation")
		set_inv(o1, custom_kitchen_status="Chưa làm", creation=add_to_date(now_datetime(), hours=-25))
		check("H6b Đã thanh toán, Chưa làm nhưng quá 24 giờ -> history",
			names(guest(C.get_my_orders, tok_a2)).get(o1) == "history")

		# ---------------- H7. Quá 30 ngày ----------------
		set_inv(o1, creation=add_to_date(now_datetime(), days=-31))
		check("H7a Đơn quá 30 ngày không hiện", o1 not in names(guest(C.get_my_orders, tok_a2)))
		set_inv(o1, creation=creation_o1, custom_kitchen_status="Chưa làm")

		# ---------------- H8. Draft hết hạn của chính phiên ----------------
		o3 = guest(C.create_order, tok_a2, cart, "Take Away")["invoice_name"]
		made["invoices"].append(o3)
		check("H8a Draft còn hạn của phiên hiện tại -> active", names(guest(C.get_my_orders, tok_a2)).get(o3) == "active")
		set_inv(o3, creation=add_to_date(now_datetime(), minutes=-20))
		check("H8b Draft quá 15 phút không hiện trong danh sách", o3 not in names(guest(C.get_my_orders, tok_a2)))

		# ---------------- H9. Mã QR chi nhánh khác ----------------
		try:
			other = "SELFTEST-BR-" + frappe.generate_hash(length=6)
			frappe.get_doc({"doctype": "Branch", "branch": other}).insert(ignore_permissions=True)
			made["branches"].append(other)
			qr2 = frappe.get_doc({"doctype": "MYPOS Order QR", "branch": other, "note": "selftest-history"}).insert()
			made["qr"].append(qr2.name)
			frappe.local.message_log = []
			tok_other, _exp = C._issue_session(cust_a, qr2.name, other, "Lich Su A")
			check("H9a Cùng khách A, mã QR chi nhánh khác -> không thấy đơn", guest(C.get_my_orders, tok_other) == [])
		except Exception as e:
			frappe.local.message_log = []
			check("H9a Không tạo được Branch/mã QR tạm để thử", False, repr(e)[:150])

		# ---------------- H10. Giới hạn tần suất ----------------
		check("H10a Cấu hình orders_mobile 60/phút, orders_ip 300/phút",
			C.RATE_LIMITS.get("orders_mobile") == (60, 60) and C.RATE_LIMITS.get("orders_ip") == (300, 60))
		frappe.cache.delete_keys("mypos_rl:")
		ok_calls, blocked = 0, False
		for _i in range(61):
			try:
				guest(C.get_my_orders, tok_a2)
				ok_calls += 1
			except C.RateLimitError:
				blocked = True
				break
		frappe.local.message_log = []
		check("H10b get_my_orders: 60 lần/phút theo SĐT, lần 61 bị chặn", ok_calls == 60 and blocked,
			f"ok={ok_calls} blocked={blocked}")
		frappe.cache.delete_keys("mypos_rl:")
		ok_login, blocked = 0, False
		for _i in range(6):
			try:
				guest(C.login, qr.token, mob_b, "Lich Su B")
				ok_login += 1
			except C.RateLimitError:
				blocked = True
				break
		frappe.local.message_log = []
		check("H10c login theo SĐT: 5 lần/10 phút, lần 6 bị chặn", ok_login == 5 and blocked,
			f"ok={ok_login} blocked={blocked}")
		frappe.cache.delete_keys("mypos_rl:")

	except Exception:
		check("Lỗi ngoài dự kiến", False)
		traceback.print_exc()
	finally:
		frappe.local.request = old_request
		frappe.set_user(admin)
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
		for name in made["branches"]:
			try:
				frappe.delete_doc("Branch", name, force=True, ignore_permissions=True)
			except Exception as e:
				print(f"Chưa dọn được Branch {name}: {e}")
		frappe.cache.delete_keys("mypos_rl:")
		frappe.db.commit()
		print(f"\nTổng (lịch sử đơn): {sum(results)}/{len(results)} PASS")

	if run_old:
		old = globals().get("run_order_qr_selftest")
		if old:
			print("\n===== Bộ cũ: run_order_qr_selftest =====")
			old(branch)
		else:
			print("Chưa dán order_qr_selftest.py nên không chạy được bộ cũ.")
