def zz_test_shop(action="create", tag=None, open_shift=True, quiet=False):
	"""Quán thử tạm cho các selfcheck GHI dữ liệu: dựng master data riêng, không đụng dữ liệu thật của quán.

	    bench --site <site> execute mypos.selfcheck.test_shop.zz_test_shop                       # create
	    bench --site <site> execute mypos.selfcheck.test_shop.zz_test_shop --kwargs "{'action': 'drop', 'tag': 'ZZTEST-...'}"
	    bench --site <site> execute mypos.selfcheck.test_shop.zz_test_shop --kwargs "{'action': 'drop'}"   # mọi quán thử ZZTEST-*
	    bench --site <site> execute mypos.selfcheck.test_shop.zz_test_shop --kwargs "{'action': 'list'}"   # liệt kê dữ liệu thử còn sót

	action = "create": kiểm điều kiện nền (`prereq_check`), thiếu -> {"ok": False, "reason"} (test gọi nó SKIP). Đủ -> tạo, mọi
	tên có tiền tố tag = "ZZTEST-<MMDDHHMMSS><3 ký tự>":
	  Item Group <tag>; Price List <tag> (VND, bán); 4 Item không tồn kho <tag>-CF 30.000, <tag>-TS 35.000 (có Option Group
	  "Đường" legacy sugar_level), <tag>-ESP 39.000 (Pricing Rule tạm 2-3 ly -5%, >= 4 ly -10%), <tag>-FREE 20.000;
	  Mode of Payment "<tag> Bank" (Bank); Customer "<tag> WI" (khách vãng lai); Branch <tag> (thương hiệu + SePay giả, API key ngẫu nhiên)
	  + 2 thẻ bàn <tag>-B1, <tag>-B2;
	  POS Profile <tag> (Cash + Bank, Applicable for Users = Administrator, branch, khách vãng lai, income_account);
	  MYPOS Menu <tag> (4 món); open_shift=True -> POS Opening Entry của Administrator (submit).
	  Commit. Trả {"ok": True, "tag", "company", "branch", "pos_profile", "price_list", "menu", "item", "item_options",
	  "item_promo", "item_free", "mop_cash", "mop_bank", "walk_in", "opening", "buzzers"}. Lỗi giữa chừng -> tự dọn phần đã tạo, ok False.
	action = "drop": xóa mọi thứ của tag (cả đơn / ca / mã QR / thẻ bàn / POS Profile gắn Branch tag do test tạo), theo thứ tự
	  phụ thuộc; mỗi lần xóa: thử lại 3 lần khi QueryDeadlockError (rollback, chờ 1 giây), commit ngay; còn sót -> in WARN.
	  tag=None -> mọi tag "ZZTEST-*" tìm thấy (Branch / Item Group).
	action = "list": chỉ đọc, đếm bản ghi thử còn sót (ZZTEST-*, "ZZTEST " của từng test, user zz.test.*).
	"""
	import secrets
	import time
	import traceback

	import frappe
	from frappe.utils import now_datetime, nowdate

	PREFIX = "ZZTEST-"
	PRICES = {"CF": 30000, "TS": 35000, "ESP": 39000, "FREE": 20000}
	DEADLOCK = getattr(frappe, "QueryDeadlockError", None) or getattr(frappe.exceptions, "QueryDeadlockError", ())

	def say(msg):
		if not quiet:
			print(msg)

	def retry_deadlock(fn, *args, **kwargs):
		for attempt in range(3):
			try:
				result = fn(*args, **kwargs)
				frappe.db.commit()
				return result
			except DEADLOCK:
				frappe.db.rollback()
				if attempt == 2:
					raise
				time.sleep(1)

	def names_of(t):
		return {
			"tag": t, "branch": t, "price_list": t, "item_group": t, "pos_profile": t, "menu": t,
			"item": f"{t}-CF", "item_options": f"{t}-TS", "item_promo": f"{t}-ESP", "item_free": f"{t}-FREE",
			"mop_bank": f"{t} Bank", "walk_in_name": f"{t} WI",
		}

	# ------------------------------------------------------------------ drop
	def drop_one(t):
		failed = []

		def delete(doctype, name, cancel=False):
			if not frappe.db.exists(doctype, name):
				return

			def _do():
				if cancel and frappe.db.get_value(doctype, name, "docstatus") == 1:
					if doctype == "POS Invoice" and frappe.db.get_value(doctype, name, "status") == "Consolidated":
						frappe.db.set_value(doctype, name, "status", "Paid", update_modified=False)
					frappe.get_doc(doctype, name).cancel()
				frappe.delete_doc(doctype, name, force=1, ignore_permissions=True)

			try:
				retry_deadlock(_do)
			except Exception as e:  # noqa: BLE001
				frappe.db.rollback()
				failed.append(f"{doctype} {name}: {str(e)[:120]}")

		frappe.db.rollback()
		profiles = set(frappe.get_all("POS Profile", filters={"branch": t}, pluck="name"))
		if frappe.db.exists("POS Profile", t):
			profiles.add(t)
		if profiles:
			for inv in frappe.get_all("POS Invoice", filters={"pos_profile": ["in", list(profiles)]}, pluck="name",
					order_by="creation desc"):
				for lpe in frappe.get_all("Loyalty Point Entry", filters={"invoice": inv}, pluck="name"):
					delete("Loyalty Point Entry", lpe)
				delete("POS Invoice", inv, cancel=True)
			for dt in ("POS Closing Entry", "POS Opening Entry"):
				for n in frappe.get_all(dt, filters={"pos_profile": ["in", list(profiles)]}, pluck="name", order_by="creation desc"):
					delete(dt, n, cancel=True)
		for dt in ("MYPOS Order QR", "MYPOS Buzzer"):
			for n in frappe.get_all(dt, filters={"branch": t}, pluck="name"):
				delete(dt, n)
		for n in frappe.get_all("MYPOS Menu", filters={"name": ["like", f"{t}%"]}, pluck="name"):
			delete("MYPOS Menu", n)
		for n in sorted(profiles):
			delete("POS Profile", n)
		for n in frappe.get_all("Pricing Rule", filters={"title": ["like", f"{t}%"]}, pluck="name"):
			delete("Pricing Rule", n)
		for n in frappe.get_all("MYPOS Option Group", filters={"title": ["like", f"{t}%"]}, pluck="name"):
			delete("MYPOS Option Group", n)
		for n in frappe.get_all("Item Price", filters={"item_code": ["like", f"{t}%"]}, pluck="name"):
			delete("Item Price", n)
		for n in frappe.get_all("Item", filters={"name": ["like", f"{t}%"]}, pluck="name"):
			delete("Item", n)
		if frappe.db.exists("Price List", t):
			delete("Price List", t)
		for n in frappe.get_all("Customer", filters={"customer_name": ["like", f"{t}%"]}, pluck="name"):
			delete("Customer", n)
		for n in frappe.get_all("Mode of Payment", filters={"name": ["like", f"{t}%"]}, pluck="name"):
			delete("Mode of Payment", n)
		delete("Branch", t)
		delete("Item Group", t)
		try:
			from mypos.mypos.doctype.mypos_option_group.option_resolver import clear_option_cache

			clear_option_cache()
		except Exception:  # noqa: BLE001
			pass
		if failed:
			say(f"WARN dọn {t} chưa hết ({len(failed)}):")
			for f in failed:
				say(f"  - {f}")
			say(f"  Xóa tay: bench --site <site> execute mypos.selfcheck.test_shop.zz_test_shop --kwargs \"{{'action': 'drop', 'tag': '{t}'}}\"")
		else:
			say(f"Đã dọn quán thử {t}")
		return failed

	def all_tags():
		tags = set(frappe.get_all("Branch", filters={"name": ["like", f"{PREFIX}%"]}, pluck="name"))
		tags |= set(frappe.get_all("Item Group", filters={"name": ["like", f"{PREFIX}%"]}, pluck="name"))
		tags |= set(frappe.get_all("Price List", filters={"name": ["like", f"{PREFIX}%"]}, pluck="name"))
		return sorted(tags)

	# ------------------------------------------------------------------ list
	def list_leftovers():
		checks = [
			("Branch", "name", "ZZTEST%"), ("POS Profile", "name", "ZZTEST%"), ("Item", "name", "ZZTEST%"),
			("Item Group", "name", "ZZTEST%"), ("Price List", "name", "ZZTEST%"), ("Customer", "customer_name", "ZZTEST%"),
			("Mode of Payment", "name", "ZZTEST%"), ("MYPOS Menu", "name", "ZZTEST%"), ("Pricing Rule", "title", "ZZTEST%"),
			("MYPOS Option Group", "title", "ZZTEST%"), ("MYPOS Buzzer", "name", "ZZT%"), ("MYPOS Banner", "title", "ZZTEST%"),
			("User", "name", "zz.test.%"), ("POS Invoice", "pos_profile", "ZZTEST%"),
			("POS Opening Entry", "pos_profile", "ZZTEST%"), ("POS Closing Entry", "pos_profile", "ZZTEST%"),
		]
		total = 0
		for dt, field, pat in checks:
			if not frappe.db.exists("DocType", dt):
				continue
			n = frappe.db.count(dt, {field: ["like", pat]})
			total += n
			if n:
				print(f"  {dt} ({field} like '{pat}'): {n} — vd {frappe.get_all(dt, filters={field: ['like', pat]}, pluck='name', limit=3)}")
		print(f"Quán thử ZZTEST-*: {all_tags() or 'không có'}")
		print(f"KẾT QUẢ: {total} bản ghi thử còn sót" if total else "KẾT QUẢ: không còn dữ liệu thử")
		return total

	# ------------------------------------------------------------------ create
	def create():
		from mypos.selfcheck.prereq_check import check_prereq

		frappe.set_user("Administrator")
		pre = check_prereq(quiet=True)
		if not pre.get("ok"):
			return {"ok": False, "reason": "Thiếu điều kiện nền: " + "; ".join(pre.get("missing") or ["?"])
				+ " (chạy mypos.selfcheck.prereq_check.check_prereq để xem cách tạo)"}
		t = PREFIX + now_datetime().strftime("%m%d%H%M%S") + frappe.generate_hash(length=3).upper()
		n = names_of(t)
		company, currency = pre["company"], pre["currency"]
		try:
			frappe.get_doc({"doctype": "Item Group", "item_group_name": t, "parent_item_group": "All Item Groups",
				"is_group": 0}).insert(ignore_permissions=True)
			frappe.get_doc({"doctype": "Price List", "price_list_name": t, "currency": currency, "selling": 1,
				"enabled": 1}).insert(ignore_permissions=True)
			for key, price in PRICES.items():
				code = f"{t}-{key}"
				frappe.get_doc({"doctype": "Item", "item_code": code, "item_name": f"{t} {key}", "item_group": t,
					"stock_uom": "Nos", "is_stock_item": 0, "is_sales_item": 1,
					"include_item_in_manufacturing": 0}).insert(ignore_permissions=True)
				frappe.get_doc({"doctype": "Item Price", "item_code": code, "price_list": t, "price_list_rate": price,
					"uom": "Nos", "selling": 1, "currency": currency}).insert(ignore_permissions=True)
			for pct, lo, hi in ((5, 2, 3), (10, 4, 0)):
				frappe.get_doc({"doctype": "Pricing Rule", "title": f"{t} CTKM {pct}%", "apply_on": "Item Code",
					"items": [{"item_code": n["item_promo"]}], "selling": 1, "price_or_product_discount": "Price",
					"rate_or_discount": "Discount Percentage", "discount_percentage": pct, "min_qty": lo, "max_qty": hi,
					"company": company, "currency": currency}).insert(ignore_permissions=True)
			frappe.get_doc({"doctype": "MYPOS Option Group", "title": f"{t} Đường", "selection_type": "Chọn 1",
				"required": 1, "enabled": 1, "legacy_field": "sugar_level",
				"values": [{"label": "50%", "sort_order": 1, "enabled": 1}, {"label": "70%", "sort_order": 2, "enabled": 1},
					{"label": "100%", "sort_order": 3, "enabled": 1, "is_default": 1}],
				"targets": [{"target_type": "Item", "item": n["item_options"]}]}).insert(ignore_permissions=True)
			frappe.get_doc({"doctype": "Mode of Payment", "mode_of_payment": n["mop_bank"], "type": "Bank", "enabled": 1,
				"accounts": [{"company": company, "default_account": pre["bank_account"]}]}).insert(ignore_permissions=True)
			walk_in = frappe.get_doc({"doctype": "Customer", "customer_name": n["walk_in_name"], "customer_type": "Individual",
				"customer_group": pre["customer_group"], "territory": pre["territory"]}).insert(ignore_permissions=True).name
			branch = frappe.get_doc({"doctype": "Branch", "branch": t})
			branch.update({"company": company, "brand_name": f"{t} Shop", "brand_phone": "0900000000",
				"brand_address": "ZZTEST", "sepay_enabled": 1, "sepay_va_account": "ZZTEST0000", "sepay_bank_code": "MB",
				"sepay_api_key": secrets.token_urlsafe(16)})
			branch.insert(ignore_permissions=True)
			for k in (1, 2):  # thẻ bàn (MYPOS Buzzer, tên = buzzer_number, duy nhất toàn site)
				frappe.get_doc({"doctype": "MYPOS Buzzer", "buzzer_number": f"{t}-B{k}", "branch": t,
					"status": "Sẵn sàng"}).insert(ignore_permissions=True)
			prof = frappe.get_doc({"doctype": "POS Profile", "company": company, "warehouse": pre["warehouse"],
				"currency": currency, "selling_price_list": t, "write_off_account": pre["write_off_account"],
				"write_off_cost_center": pre["cost_center"], "write_off_limit": 1, "cost_center": pre["cost_center"],
				"income_account": pre["income_account"], "branch": t, "custom_walk_in_customer": walk_in,
				"payments": [{"mode_of_payment": pre["mop_cash"], "default": 1}, {"mode_of_payment": n["mop_bank"]}],
				"applicable_for_users": [{"user": "Administrator", "default": 0}]})
			prof.set("__newname", t)
			prof.insert(ignore_permissions=True)
			frappe.get_doc({"doctype": "MYPOS Menu", "menu_name": t, "price_list": t, "currency": currency,
				"items": [{"item_code": f"{t}-{k}"} for k in PRICES]}).insert(ignore_permissions=True)
			opening = None
			if open_shift:
				op = frappe.get_doc({"doctype": "POS Opening Entry", "period_start_date": now_datetime(), "posting_date": nowdate(),
					"company": company, "pos_profile": t, "user": "Administrator",
					"balance_details": [{"mode_of_payment": pre["mop_cash"], "opening_amount": 0}]})
				op.insert(ignore_permissions=True)
				op.submit()
				opening = op.name
			frappe.db.commit()
		except Exception as e:  # noqa: BLE001
			frappe.db.rollback()
			short = "".join(traceback.format_exception_only(type(e), e)).strip()[:300]
			say(f"LỖI dựng quán thử {t}: {short}")
			drop_one(t)
			return {"ok": False, "reason": f"Không dựng được quán thử: {short}"}
		say(f"Đã dựng quán thử {t} (Company {company}, ca mở: {opening or 'không'})")
		return {"ok": True, "company": company, "walk_in": walk_in, "mop_cash": pre["mop_cash"], "opening": opening,
			"buzzers": [f"{t}-B1", f"{t}-B2"], **n}

	if action == "create":
		return create()
	if action == "drop":
		tags = [tag] if tag else all_tags()
		left = {}
		for t in tags:
			left[t] = drop_one(t)
		if not tags:
			say("Không có quán thử ZZTEST-* nào")
		return left
	if action == "list":
		return list_leftovers()
	raise ValueError(f"action không hợp lệ: {action!r} (create / drop / list)")
