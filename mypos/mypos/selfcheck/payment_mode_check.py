def check_payment_modes():
	"""Mode of Payment theo POS Profile + menu không trùng + khách mặc định (2026-11-28).

	    bench --site <site> execute mypos.selfcheck.payment_mode_check.check_payment_modes

	Dựng 2 quán thử ZZTEST-* (test_shop.py), mỗi quán: Mode of Payment "<tag> Cash" (Cash) + "<tag> Bank" (Bank) riêng,
	POS Profile chỉ có 2 mode đó (quán A đặt dòng Bank TRƯỚC dòng Cash nhưng Cash là Default), user tạm
	zz.test.paymode.<a|b>@example.com (POS CASHIER, Default ở profile quán mình). Kiểm:
	  M1 get_pos_config: chỉ mode của profile, Default đứng đầu, không có mode ngoài profile (vd "Cash" có sẵn của ERPNext).
	  M2 create_draft_order không truyền mode -> mode Cash của profile (đúng chi nhánh, đúng tài khoản).
	  M3 truyền mode ngoài profile (mode quán kia / mode "Cash" ERPNext) -> bị chặn.
	  M4 pay_cash trên đơn Draft đang mang mode ngoài profile (giả lập đơn cũ) -> submit với mode Cash của profile.
	  M5 generate_qr -> dòng thanh toán = mode Bank của profile; /order _transfer_mode = mode Bank của profile.
	  M6 profile không có mode Bank -> lỗi rõ (pos_api) / thông báo chung (/order); không lấy mode Bank ngoài profile.
	  N1 get_menu_items() không truyền Price List -> chỉ menu theo Price List bán của profile, không trùng món.
	  C1 tạo đơn không chọn khách -> khách vãng lai của profile; chọn khách -> đúng khách đã chọn.
	Dọn: drop 2 quán thử (đơn, ca, profile, mode...), rồi xóa user tạm (Contact trước User); thử lại khi deadlock.
	"""
	import time

	import frappe

	from mypos.mypos.api import customer_order_api as Q
	from mypos.mypos.api import pos_api as P
	from mypos.selfcheck.test_shop import zz_test_shop

	DEADLOCK = getattr(frappe, "QueryDeadlockError", None) or getattr(frappe.exceptions, "QueryDeadlockError", ())
	results, shops, users = [], {}, {}

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

	def pay_row(inv_name):
		rows = frappe.get_all("Sales Invoice Payment", filters={"parent": inv_name, "parenttype": "POS Invoice"},
			fields=["mode_of_payment", "account"])
		return [(r.mode_of_payment, r.account) for r in rows]

	def delete_user(email):
		for _attempt in range(3):
			try:
				frappe.db.commit()
				for c in frappe.get_all("Contact", filters={"user": email}, pluck="name"):
					frappe.delete_doc("Contact", c, force=1, ignore_permissions=True)
				if frappe.db.exists("User", email):
					frappe.delete_doc("User", email, force=1, ignore_permissions=True)
				frappe.db.commit()
				return
			except DEADLOCK:
				frappe.db.rollback()
				time.sleep(1)
			except Exception as e:  # noqa: BLE001
				frappe.db.rollback()
				print(f"WARN: không xóa được user {email}: {type(e).__name__}: {str(e)[:150]}")
				return
		print(f"WARN: không xóa được user {email} sau 3 lần thử (deadlock)")

	frappe.set_user("Administrator")
	try:
		for key in ("A", "B"):
			shop = zz_test_shop("create", open_shift=False, quiet=True)
			if not shop.get("ok"):
				print(f"SKIP: {shop.get('reason')}")
				print("KẾT QUẢ: SKIP")
				return None
			shops[key] = shop
		company = shops["A"]["company"]
		cash_account = frappe.db.get_value("Mode of Payment Account",
			{"parent": shops["A"]["mop_cash"], "company": company}, "default_account")
		for key, shop in shops.items():
			t = shop["tag"]
			shop["cash"] = f"{t} Cash"
			frappe.get_doc({"doctype": "Mode of Payment", "mode_of_payment": shop["cash"], "type": "Cash", "enabled": 1,
				"accounts": [{"company": company, "default_account": cash_account}]}).insert(ignore_permissions=True)
			email = f"zz.test.paymode.{key.lower()}@example.com"
			if frappe.db.exists("User", email):
				delete_user(email)
			frappe.get_doc({"doctype": "User", "email": email, "first_name": f"ZZTEST PayMode {key}",
				"user_type": "System User", "send_welcome_email": 0, "enabled": 1,
				"roles": [{"role": "POS CASHIER"}]}).insert(ignore_permissions=True)
			users[key] = email
			prof = frappe.get_doc("POS Profile", shop["pos_profile"])
			rows = [{"mode_of_payment": shop["cash"], "default": 1}, {"mode_of_payment": shop["mop_bank"], "default": 0}]
			if key == "A":  # dòng Bank đứng trước nhưng Cash là Default -> Default vẫn phải đứng đầu
				rows.reverse()
			prof.set("payments", rows)
			prof.set("applicable_for_users", [{"user": email, "default": 1}])
			prof.save(ignore_permissions=True)
		frappe.db.commit()

		line = lambda shop: [{"item_code": shop["item"], "qty": 1}]  # noqa: E731

		# M1 — get_pos_config
		for key, shop in shops.items():
			cfg, err = as_user(key, P.get_pos_config)
			names = [m["name"] for m in (cfg or {}).get("payment_modes", [])]
			ok(f"M1-{key} get_pos_config chỉ mode của profile, Default đầu", err is None and names == [shop["cash"], shop["mop_bank"]],
				f"-> {names or err}")
			ok(f"M1-{key} không có mode ngoài profile", shop["mop_cash"] not in names, f"-> {names}")

		# M2 + C1 — tạo đơn không truyền mode / không chọn khách
		drafts = {}
		for key, shop in shops.items():
			res, err = as_user(key, P.create_draft_order, line(shop), "Take Away", price_list=shop["price_list"])
			inv = (res or {}).get("invoice_name")
			drafts[key] = inv
			ok(f"M2-{key} đơn mới ghi mode Cash của profile", inv and pay_row(inv) == [(shop["cash"], cash_account)],
				f"-> {pay_row(inv) if inv else err}")
			ok(f"C1-{key} không chọn khách -> khách vãng lai của profile",
				inv and frappe.db.get_value("POS Invoice", inv, "customer") == shop["walk_in"],
				f"-> {frappe.db.get_value('POS Invoice', inv, 'customer') if inv else err}")
		res, err = as_user("A", P.create_draft_order, line(shops["A"]), "Take Away", customer_name=shops["B"]["walk_in"],
			price_list=shops["A"]["price_list"])
		inv = (res or {}).get("invoice_name")
		ok("C1-A chọn khách -> đúng khách đã chọn", inv and frappe.db.get_value("POS Invoice", inv, "customer") == shops["B"]["walk_in"],
			f"-> {frappe.db.get_value('POS Invoice', inv, 'customer') if inv else err}")

		# M3 — mode ngoài profile bị chặn
		_r, err = as_user("A", P.create_draft_order, line(shops["A"]), "Take Away", mode_of_payment=shops["B"]["cash"],
			price_list=shops["A"]["price_list"])
		blocked("M3 mode của quán khác bị chặn", err, "không thuộc POS Profile")
		_r, err = as_user("A", P.create_draft_order, line(shops["A"]), "Take Away", mode_of_payment=shops["A"]["mop_cash"],
			price_list=shops["A"]["price_list"])
		blocked("M3 mode 'Cash' có sẵn ngoài profile bị chặn", err, "không thuộc POS Profile")

		# M4 — pay_cash sửa mode của đơn cũ mang mode ngoài profile
		inv = drafts["A"]
		row = frappe.get_all("Sales Invoice Payment", filters={"parent": inv, "parenttype": "POS Invoice"}, pluck="name")[0]
		frappe.db.set_value("Sales Invoice Payment", row, {"mode_of_payment": shops["A"]["mop_cash"], "account": cash_account})
		frappe.db.commit()
		_r, err = as_user("A", P.pay_cash, inv)
		ok("M4 pay_cash -> mode Cash của profile + Paid",
			err is None and pay_row(inv) == [(shops["A"]["cash"], cash_account)]
			and frappe.db.get_value("POS Invoice", inv, "status") == "Paid",
			f"-> {pay_row(inv)} {frappe.db.get_value('POS Invoice', inv, 'status')} {err or ''}")

		# M5 — sinh QR + /order dùng mode Bank của profile
		bank_acc = frappe.db.get_value("Mode of Payment Account", {"parent": shops["B"]["mop_bank"], "company": company},
			"default_account")
		inv = drafts["B"]
		_r, err = as_user("B", P.generate_qr, inv)
		ok("M5 generate_qr -> mode Bank của profile", err is None and pay_row(inv) == [(shops["B"]["mop_bank"], bank_acc)],
			f"-> {pay_row(inv)} {err or ''}")
		for key, shop in shops.items():
			mode = Q._transfer_mode(frappe.get_doc("POS Profile", shop["pos_profile"]))
			ok(f"M5-{key} /order _transfer_mode = mode Bank của profile", mode["name"] == shop["mop_bank"], f"-> {mode['name']}")

		# M6 — profile không có mode Bank
		prof = frappe.get_doc("POS Profile", shops["B"]["pos_profile"])
		prof.set("payments", [{"mode_of_payment": shops["B"]["cash"], "default": 1}])
		prof.save(ignore_permissions=True)
		frappe.db.commit()
		prof = frappe.get_doc("POS Profile", shops["B"]["pos_profile"])
		try:
			P._resolve_mode_of_payment(prof, mode_type="Bank")
			err = None
		except Exception as e:  # noqa: BLE001
			frappe.clear_messages()
			err = e
		blocked("M6 thiếu mode Bank -> lỗi rõ", err, "chưa có phương thức thanh toán", "chuyển khoản")
		try:
			Q._transfer_mode(prof)
			err = None
		except Exception as e:  # noqa: BLE001
			frappe.clear_messages()
			err = e
		blocked("M6 /order thiếu mode Bank -> thông báo chung, không lấy mode ngoài profile", err, "chưa cấu hình thanh toán chuyển khoản")

		# N1 — menu theo Price List của profile, không trùng
		for key, shop in shops.items():
			menus, err = as_user(key, P.get_menu_items)
			pls = {m["price_list"] for m in (menus or [])}
			names = [it["name"] for m in (menus or []) for it in m["items"]]
			ok(f"N1-{key} get_menu_items chỉ menu của profile", err is None and pls == {shop["price_list"]}, f"-> {pls or err}")
			ok(f"N1-{key} không trùng món", names and len(names) == len(set(names)), f"-> {len(names)} món, {len(set(names))} khác nhau")
	finally:
		frappe.set_user("Administrator")
		try:
			frappe.db.rollback()
		except Exception:  # noqa: BLE001
			pass
		for shop in shops.values():
			zz_test_shop("drop", shop["tag"], quiet=True)
		for email in users.values():
			delete_user(email)

	fails = [c for c, r in results if not r]
	print(f"KẾT QUẢ: {'PASS' if not fails else 'FAIL'} ({len(results) - len(fails)}/{len(results)})"
		+ (f" — lỗi: {', '.join(fails)}" if fails else ""))
	return {"ok": not fails, "results": results}
