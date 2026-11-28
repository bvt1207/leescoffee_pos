def check_option_surcharge(mode_of_payment=None, price_list=None, esp1=None,
                           branch_name=None, customer=None, free_item_code=None):
	"""Phụ thu tùy chọn món (topping) — cộng SAU CTKM qua một dòng Taxes and Charges kiểu Actual.

	Dán CẢ hàm vào `bench --site <site> console` rồi gọi, ví dụ:
	    check_option_surcharge("<Mode of Payment chuyển khoản>", "<Price List của MYPOS Menu>", "<mã món có CTKM>",
	                           branch_name="<Branch>", customer="<Customer có điểm Loyalty, bỏ trống = SKIP E>")

	Cần: Administrator có ca POS đang mở cho POS Profile (script không mở ca mới); món `esp1` có CTKM
	qty 2-3 giảm 5%, qty >= 4 giảm 10% (như task CTKM). Tự tạo Option Group / Order QR / Pricing Rule tạm (tiền tố
	ZZTEST), mọi thứ ROLLBACK cuối hàm; nếu có commit ngầm (webhook) thì tự hủy + xóa và in WARN.
	KHÔNG chạy đóng ca (sẽ gộp đơn thật) — xem checklist tay.
	free_item_code: mã món (khác `esp1`, không có CTKM khác) để dựng luật "mua 2 tặng 1" thử; bỏ trống = SKIP.
	Khách vãng lai (2026-11-24): đơn thử dùng Customer TẠM "ZZTEST WI ..." do script tự tạo và tự xóa — không cần POS Profile
	thật đã cấu hình Khách vãng lai, không dùng Customer thật nào.
	"""
	if mode_of_payment is None:  # không truyền dữ liệu -> tự dựng quán thử tạm (selfcheck/test_shop.py), dọn ở cuối
		from mypos.selfcheck.test_shop import zz_test_shop

		_shop = zz_test_shop("create", open_shift=True)
		if not _shop.get("ok"):
			print(f"SKIP: {_shop.get('reason')}")
			print("KẾT QUẢ: SKIP")
			return None
		try:
			return check_option_surcharge(_shop["mop_bank"], _shop["price_list"], _shop["item_promo"], branch_name=_shop["branch"], customer=customer, free_item_code=_shop["item_free"])
		finally:
			zz_test_shop("drop", _shop["tag"])

	import json
	import traceback

	import frappe
	from frappe.utils import flt
	from frappe.utils.password import get_decrypted_password

	from mypos.mypos.api import customer_order_api as C
	from mypos.mypos.api import pos_api as P
	from mypos.mypos.doctype.mypos_option_group.option_resolver import clear_option_cache
	from mypos.mypos.doctype.sepay import sepay as S

	# Dọn dữ liệu thử: QueryDeadlockError (MariaDB 1213 / 1020) -> rollback, chờ 1 giây, thử lại (tối đa 3 lần);
	# thành công -> commit ngay (bản ghi đã xóa không bị rollback lần thử sau cuốn mất). Lỗi khác ném lại cho khối gọi.
	DEADLOCK = getattr(frappe, "QueryDeadlockError", None) or getattr(frappe.exceptions, "QueryDeadlockError", ())

	def retry_deadlock(fn, *args, **kwargs):
		import time as _time

		for attempt in range(3):
			try:
				result = fn(*args, **kwargs)
				frappe.db.commit()
				return result
			except DEADLOCK:
				frappe.db.rollback()
				if attempt == 2:
					raise
				_time.sleep(1)

	TOPPING_TITLE = "ZZTEST Topping phụ thu"
	T10, T5, TOFF = "ZZ Trân châu", "ZZ Thạch", "ZZ Tắt"
	results, made_inv, made_docs = [], [], []
	wi_box = {"c": None}  # Customer tạm khi đơn thử không chọn khách (2026-11-24)

	def money(v):
		return f"{flt(v):,.0f}".replace(",", ".")

	def ok(case, cond, extra=""):
		results.append((case, bool(cond)))
		print(f"{'PASS' if cond else 'FAIL'} {case} {extra}")

	def total(x):
		return round(flt(x["grand_total"] if isinstance(x, dict) else x.grand_total))

	def surcharge_rows(name):
		return frappe.get_all("Sales Taxes and Charges", filters={"parent": name, "parenttype": "POS Invoice",
			"description": P.SURCHARGE_DESCRIPTION}, fields=["tax_amount", "charge_type", "account_head"])

	def L(qty, opts=None, code=None):
		return {"item_code": code or esp1, "qty": qty, "options": opts if opts is not None else []}

	def top(*labels):
		return [{"group": grp.name, "value": list(labels)}] if labels else []

	def preview(rows, customer=None, **kw):
		"""preview_pricing với khách tạm khi không chọn khách (không phụ thuộc Khách vãng lai của POS Profile thật)."""
		return P.preview_pricing(rows, customer=customer or wi_box["c"], **kw)

	def run_case(case, rows, expected, pay=False, customer_=None, redeem=0):
		p = preview(rows, customer=customer_, price_list=price_list, redeem_points=redeem)
		res = P.create_draft_order(items=rows, order_type="Take Away", customer_name=customer_ or wi_box["c"],
			mode_of_payment=mode_of_payment, branch_name=branch_name, price_list=price_list, redeem_points=redeem)
		made_inv.append(res["invoice_name"])
		inv = frappe.get_doc("POS Invoice", res["invoice_name"])
		ok(f"{case}: preview = hóa đơn sau tạo", total(p) == total(inv), f"({money(total(p))} / {money(total(inv))})")
		if pay:
			P.pay_cash(inv.name)
			inv.reload()
			ok(f"{case}: preview = hóa đơn sau pay_cash", total(p) == total(inv), f"({money(total(inv))})")
		rows_s = surcharge_rows(inv.name)
		ok(f"{case}: mong đợi {money(expected)}", total(inv) == expected,
			f"được {money(total(inv))}; phụ thu preview {money(p.get('total_surcharge'))}, dòng phụ thu {[(r.charge_type, flt(r.tax_amount)) for r in rows_s]}")
		ok(f"{case}: tối đa 1 dòng phụ thu, khớp preview", len(rows_s) <= 1 and
			round(sum(flt(r.tax_amount) for r in rows_s)) == round(flt(p.get("total_surcharge"))))
		return p, inv

	def expect_err(case, fn, contains):
		try:
			fn()
			ok(case, False, "-> KHÔNG lỗi")
		except Exception as e:  # noqa: BLE001
			frappe.clear_messages()
			ok(case, contains.lower() in str(e).lower(), f"-> {type(e).__name__}: {str(e)[:110]}")

	frappe.set_user("Administrator")
	profile = P._get_pos_profile(branch_name)
	branch = profile.branch
	if not frappe.get_all("POS Opening Entry", filters={"pos_profile": profile.name, "user": "Administrator",
			"status": "Open", "docstatus": 1}, limit=1):
		print(f"DỪNG: Administrator chưa có ca mở cho POS Profile {profile.name} (script không mở ca mới).")
		return
	orig_profile = frappe.db.get_value("POS Profile", profile.name, ["income_account", "taxes_and_charges"], as_dict=True)
	orig_company_income = frappe.db.get_value("Company", profile.company, "default_income_account")
	print(f"INFO POS Profile {profile.name}, branch {branch}, income_account={orig_profile.income_account}, "
		f"company default_income_account={orig_company_income}, mẫu thuế={orig_profile.taxes_and_charges}")
	match = frappe.db.get_value("Item", esp1, "variant_of") or esp1

	try:
		grp = frappe.get_doc({
			"doctype": "MYPOS Option Group", "title": TOPPING_TITLE, "selection_type": "Chọn nhiều",
			"required": 0, "enabled": 1, "legacy_field": "none",
			"values": [{"label": T10, "extra_price": 10000, "enabled": 1, "sort_order": 1},
				{"label": T5, "extra_price": 5000, "enabled": 1, "sort_order": 2},
				{"label": TOFF, "extra_price": 7000, "enabled": 0, "sort_order": 3}],
			"targets": [{"target_type": "Item", "item": match}],
		}).insert(ignore_permissions=True)
		made_docs.append(("MYPOS Option Group", grp.name))
		# Khách TẠM (2026-11-24): đơn thử chọn khách rõ, không phụ thuộc Khách vãng lai của POS Profile thật.
		_wi = frappe.new_doc("Customer")
		_wi.customer_name = f"ZZTEST WI Surcharge {frappe.generate_hash(length=6)}"
		_wi.customer_type = "Individual"
		_wi.customer_group = frappe.db.get_single_value("Selling Settings", "customer_group") or "Individual"
		_wi.territory = frappe.db.get_single_value("Selling Settings", "territory") or "All Territories"
		_wi.insert(ignore_permissions=True)
		wi_box["c"] = _wi.name
		made_docs.append(("Customer", wi_box["c"]))
		clear_option_cache()

		print("== A. Không topping: giữ số cũ ==")
		run_case("A1 x1", [L(1)], 39000)
		run_case("A2 x2", [L(2)], 74100)
		run_case("A3 x4", [L(4)], 140400)

		print("== B. Có topping ==")
		run_case("B1 x1 + Trân châu 10.000", [L(1, top(T10))], 49000)
		_p, b2 = run_case("B2 x4 + Trân châu", [L(4, top(T10))], 180400, pay=True)
		_p, b3 = run_case("B3 2 dòng: 2×Trân châu + 2×Thạch", [L(2, top(T10)), L(2, top(T5))], 170400, pay=True)
		ok("B3 hai dòng vẫn giảm 10% (CTKM theo tổng qty, phụ thu không đếm vào luật)",
			all(flt(r.discount_percentage) == 10 for r in b3.items), str([flt(r.discount_percentage) for r in b3.items]))
		run_case("B4 chọn nhiều: x1 + Trân châu + Thạch", [L(1, top(T10, T5))], 54000)
		ok("B5 menu trả extra_price", any(
			v.get("extra_price") == 10000 for m in P.get_menu_items(price_list) for it in m["items"]
			for g in it.get("option_groups", []) if g["name"] == grp.name for v in g["values"]))

		print("== C. Từ chối ==")
		expect_err("C1 giá trị đã tắt", lambda: preview([L(1, top(TOFF))], price_list=price_list), "không thuộc nhóm")
		expect_err("C2 nhóm không áp dụng", lambda: preview(
			[L(1, [{"group": "MYPOS-OPT-ZZKHONGCO", "value": T10}])], price_list=price_list), "không áp dụng")

		print("== D. Idempotent ==")
		inv = frappe.get_doc("POS Invoice", b3.name)
		P._apply_option_surcharge(inv, profile)
		P._apply_option_surcharge(inv, profile)
		rows_d = [t for t in inv.taxes if P._is_surcharge_row(t)]
		ok("D1 gọi 3 lần vẫn 1 dòng, cùng số tiền", len(rows_d) == 1 and round(flt(rows_d[0].tax_amount)) == 30000)
		for r in inv.items:
			r.options = "[]"
		P._apply_option_surcharge(inv, profile)
		ok("D2 tổng 0 -> xóa dòng phụ thu cũ", not [t for t in inv.taxes if P._is_surcharge_row(t)])

		print("== E. Đổi điểm + topping ==")
		cust = customer and (frappe.db.exists("Customer", customer) or frappe.db.get_value(
			"Customer", {"customer_name": ["like", f"%{customer}%"]}, "name"))
		info = P._loyalty_info(cust, profile.company, 49000) if cust else None
		if not info or info["max_redeem_points"] < 1:
			print(f"SKIP E: khách '{customer}' không có chương trình/điểm ({info})")
		else:
			cf = info["conversion_factor"]
			p, _inv = run_case(f"E1 x1 + Trân châu, đổi 1 điểm ({cust})", [L(1, top(T10))], round(49000 - cf),
				pay=True, customer_=cust, redeem=1)
			ok("E2 điểm tối đa theo tổng sau luật + phụ thu (49.000)", p["max_redeem_points"] == info["max_redeem_points"],
				f"preview {p['max_redeem_points']}, mong đợi {info['max_redeem_points']}")

		print("== F. Webhook (đơn QR) ==")
		api_key = get_decrypted_password("Branch", branch, "sepay_webhook_secret", raise_exception=False)
		if not api_key:
			print("SKIP F: Branch chưa có sepay_webhook_secret")
		else:
			qr = frappe.get_doc({"doctype": "MYPOS Order QR", "branch": branch, "note": "ZZTEST surcharge"}).insert()
			made_docs.append(("MYPOS Order QR", qr.name))
			qcust = cust or frappe.db.get_value("Customer", {"disabled": 0}, "name")
			tok, _exp = C._issue_session(qcust, qr.name, branch, "ZZTEST")
			cart = [L(2, top(T10)), L(2, top(T5))]
			frappe.set_user("Guest")
			try:
				pv = C.preview(tok, json.dumps(cart))
				order = C.create_order(tok, json.dumps(cart), "Take Away")
				pq = C.create_payment_qr(tok, order["invoice_name"])
			finally:
				frappe.set_user("Administrator")
			made_inv.append(order["invoice_name"])
			qinv = frappe.get_doc("POS Invoice", order["invoice_name"])
			ok("F1 preview QR = đơn QR", total(pv) == total(qinv) == 170400, f"({money(total(pv))} / {money(total(qinv))})")
			from mypos.selfcheck.sepay_sign import webhook_request

			old_req = getattr(frappe.local, "request", None)
			frappe.local.request = webhook_request({"content": pq["payment_code"], "transferAmount": flt(pq["amount"]),
				"id": "ZZTEST-" + frappe.generate_hash(length=8), "transferType": "in", "gateway": "TEST"}, api_key)
			frappe.local.request_ip = "127.0.0.1"
			frappe.set_user("Guest")
			try:
				S.sepay_webhook()
			finally:
				frappe.set_user("Administrator")
				frappe.local.request = old_req
			qinv.reload()
			ok("F2 sau webhook: Paid, tổng = preview, dòng phụ thu còn",
				qinv.docstatus == 1 and total(qinv) == total(pv) and len(surcharge_rows(qinv.name)) == 1,
				f"docstatus {qinv.docstatus}, {money(total(qinv))}")

		print("== G. Đổi giá topping sau khi bán ==")
		before = round(sum(flt(r.tax_amount) for r in surcharge_rows(b2.name)))
		grp.reload()
		for v in grp.values:
			if v.label == T10:
				v.extra_price = 20000
		grp.save(ignore_permissions=True)
		after = round(sum(flt(r.tax_amount) for r in surcharge_rows(b2.name)))
		detail = P.get_order_detail(b2.name)
		ok("G1 đơn cũ giữ phụ thu cũ (40.000), JSON giữ 10.000", before == after == 40000 and detail["total_surcharge"] == 40000
			and all(o["price"] == 10000 for it in detail["items"] for o in it["options"] if o["value"] == T10),
			f"trước {money(before)}, sau {money(after)}")
		ok("G2 đơn mới dùng giá mới: x1 + Trân châu = 59.000",
			total(preview([L(1, top(T10))], price_list=price_list)) == 59000)
		k = [o for o in P.get_kitchen_orders() if o["name"] == b2.name]
		ok("G3 get_kitchen_orders có price trong options", bool(k) and k[0]["items"][0]["options"][0]["price"] == 10000)

		print("== H. Hủy Draft / job hủy đơn QR quá hạn: đơn Cancelled, dòng phụ thu giữ nguyên theo đơn ==")
		# 2026-11-23: hủy KHÔNG xóa đơn (order_cancel.cancel_draft) -> dòng phụ thu còn, cùng docstatus 2 với đơn.
		from mypos.mypos.doctype.pos_invoice_hooks import order_cancel as OC

		# Mục G đã đổi giá Trân châu thành 20.000 -> đơn H0 / H2 mang phụ thu 20.000 (tổng 59.000).
		t10_now = next(flt(v.extra_price) for v in frappe.get_doc("MYPOS Option Group", grp.name).values if v.label == T10)

		def cancelled_with_surcharge(name):
			rows = frappe.get_all("Sales Taxes and Charges", filters={"parent": name, "parenttype": "POS Invoice",
				"description": P.SURCHARGE_DESCRIPTION}, fields=["tax_amount", "docstatus"])
			return frappe.db.get_value("POS Invoice", name, "docstatus") == 2 and len(rows) == 1 \
				and flt(rows[0].tax_amount) == t10_now and rows[0].docstatus == 2

		_p, h1 = run_case("H0 tạo đơn để hủy", [L(1, top(T10))], 59000)
		P.cancel_draft_order(h1.name, 1, "Đặt nhầm")
		ok(f"H1 cancel_draft_order: đơn Cancelled, 1 dòng phụ thu {money(t10_now)} (docstatus 2), không nhân đôi",
			cancelled_with_surcharge(h1.name))
		_p, h2 = run_case("H2 tạo đơn để job hủy", [L(1, top(T10))], 59000)
		OC.cancel_draft(h2.name, OC.REASON_QR_EXPIRED, OC.SOURCE_AUTO_QR)  # cùng hàm job auto_cancel_qr_drafts dùng
		ok("H3 cancel_draft (như job hủy đơn QR): đơn Cancelled, dòng phụ thu giữ nguyên", cancelled_with_surcharge(h2.name))

		print("== I. Mẫu thuế trên POS Profile ==")
		tpl = frappe.db.get_value("Sales Taxes and Charges Template", {"company": profile.company, "disabled": 0}, "name")
		if not tpl:
			print("SKIP I: công ty chưa có Sales Taxes and Charges Template")
		else:
			frappe.db.set_value("POS Profile", profile.name, "taxes_and_charges", tpl)
			g0 = preview([L(1)], price_list=price_list)
			g1 = preview([L(1, top(T10))], price_list=price_list)
			ok(f"I1 mẫu thuế {tpl}: phụ thu cộng nguyên, không chịu thuế %",
				round(total(g1) - total(g0)) == 20000, f"không topping {money(total(g0))}, có topping {money(total(g1))}")
			frappe.db.set_value("POS Profile", profile.name, "taxes_and_charges", orig_profile.taxes_and_charges)

		print("== J. Thiếu tài khoản doanh thu ==")
		frappe.db.set_value("POS Profile", profile.name, "income_account", None)
		frappe.db.set_value("Company", profile.company, "default_income_account", None)
		expect_err("J1 có topping mà thiếu income_account -> báo lỗi rõ",
			lambda: preview([L(1, top(T10))], price_list=price_list), "tài khoản doanh thu")
		ok("J2 không topping vẫn tính bình thường", total(preview([L(1)], price_list=price_list)) == 39000)
		frappe.db.set_value("POS Profile", profile.name, "income_account", orig_profile.income_account)
		frappe.db.set_value("Company", profile.company, "default_income_account", orig_company_income)

		print("== K. Mua tặng sản phẩm ==")
		if not free_item_code:
			print("SKIP K: chưa truyền free_item_code")
		else:
			fmatch = frappe.db.get_value("Item", free_item_code, "variant_of") or free_item_code
			grp.reload()
			grp.append("targets", {"target_type": "Item", "item": fmatch})
			grp.save(ignore_permissions=True)
			pr = frappe.get_doc({"doctype": "Pricing Rule", "title": "ZZTEST mua 2 tặng 1", "apply_on": "Item Code",
				"items": [{"item_code": free_item_code}], "price_or_product_discount": "Product", "selling": 1,
				"min_qty": 2, "same_item": 1, "free_qty": 1, "company": profile.company, "priority": 20,
				"applicable_for": ""}).insert(ignore_permissions=True)
			made_docs.append(("Pricing Rule", pr.name))
			pk = preview([L(2, top(T10), free_item_code)], price_list=price_list)
			free_rows = [i for i in pk["items"] if i["is_free_item"]]
			ok("K1 có dòng tặng; phụ thu chỉ cho 2 ly trả tiền (2 × 20.000)", bool(free_rows) and round(pk["total_surcharge"]) == 40000,
				f"dòng tặng {len(free_rows)}, phụ thu {money(pk['total_surcharge'])}")
	except Exception:
		ok("Lỗi ngoài dự kiến", False)
		traceback.print_exc()
	finally:
		frappe.set_user("Administrator")
		frappe.db.rollback()
		clear_option_cache()
		left_inv = [n for n in made_inv if frappe.db.exists("POS Invoice", n)]
		left_docs = [(dt, n) for dt, n in made_docs if frappe.db.exists(dt, n)]
		for n in left_inv:
			try:
				def _drop(n=n):
					d = frappe.get_doc("POS Invoice", n)
					if d.docstatus == 1:
						d.cancel()
					frappe.delete_doc("POS Invoice", n, force=1, ignore_permissions=True)

				retry_deadlock(_drop)
			except Exception as e:  # noqa: BLE001
				print(f"WARN không dọn được {n}: {e} (hủy/xóa tay trên Desk)")
		for dt, n in left_docs:
			try:
				retry_deadlock(frappe.delete_doc, dt, n, force=1, ignore_permissions=True)
			except Exception as e:  # noqa: BLE001
				print(f"WARN không dọn được {dt} {n}: {e} (xóa tay trên Desk)")
		cur = frappe.db.get_value("POS Profile", profile.name, ["income_account", "taxes_and_charges"], as_dict=True)
		if cur != orig_profile or frappe.db.get_value("Company", profile.company, "default_income_account") != orig_company_income:
			frappe.db.set_value("POS Profile", profile.name, "income_account", orig_profile.income_account)
			frappe.db.set_value("POS Profile", profile.name, "taxes_and_charges", orig_profile.taxes_and_charges)
			frappe.db.set_value("Company", profile.company, "default_income_account", orig_company_income)
			print("WARN đã trả lại income_account / mẫu thuế / default_income_account (có commit ngầm)")
		if left_inv or left_docs:
			frappe.db.commit()
			print(f"WARN có commit ngầm, đã dọn: đơn {left_inv}, bản ghi {left_docs}")
		else:
			print("Đã rollback: không còn dữ liệu thử")

	print("\n== TÓM TẮT ==")
	n_fail = sum(1 for _c, good in results if not good)
	for case, good in results:
		if not good:
			print("FAIL " + case)
	print("KẾT QUẢ:", "PASS" if results and not n_fail else f"FAIL ({n_fail})", f"— {len(results)} kiểm tra")
	return results
