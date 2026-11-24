def check_legacy_options(item_plain, item_with_options, mode_of_payment, branch_name=None, price_list=None):
	"""Món không có Option Group không còn hiện "Đường 100% · Đá 100%"; đơn cũ vẫn dựng từ cột cũ.

	Dán CẢ hàm vào `bench --site <site> console` (SAU khi migrate) rồi gọi, ví dụ:
	    check_legacy_options("<món không Option Group>", "<món có Đường/Đá>", "Cash",
	                         branch_name="<tên Branch>", price_list="<Price List của MYPOS Menu>")

	Cần: Administrator có ca POS đang mở cho POS Profile (script KHÔNG mở ca). price_list bỏ trống = selling_price_list
	của POS Profile. Tạo vài đơn Take Away thử, cuối hàm ROLLBACK; nếu có commit ngầm thì hủy + xóa đơn và in WARN.
	Mục G chỉ ĐỌC (không sửa đơn cũ). Sau khi PASS: chạy lại run_order_qr_selftest(), run_order_history_selftest(),
	check_option_surcharge(...).
	Khách vãng lai (2026-11-24): đơn thử dùng Customer TẠM "ZZTEST WI ..." do script tự tạo và tự xóa — không cần POS Profile
	thật đã cấu hình Khách vãng lai, không dùng Customer thật nào.
	"""
	import json
	import traceback

	import frappe

	from leescoffee_pos.leescoffee_pos.api import customer_order_api as C
	from leescoffee_pos.leescoffee_pos.api import pos_api as P
	from leescoffee_pos.leescoffee_pos.doctype.mypos_option_group.option_resolver import (
		read_line_options,
		resolve_option_groups,
	)

	results, made_inv = [], []
	ctx = {"price_list": price_list, "walk_in": None}

	def ok(case, cond, extra=""):
		results.append((case, bool(cond)))
		print(f"{'PASS' if cond else 'FAIL'} {case} {extra}")

	def labels(opts):
		return " · ".join(f"{o['group_title']} {o['value']}" for o in opts)

	def make(code, options=None, legacy_request=False, pay=False):
		line = {"item_code": code, "qty": 1}
		if legacy_request:
			line.update({"sugar": 70, "ice": 50})  # frontend cũ: không có khóa options
		else:
			line["options"] = options if options is not None else []
		res = P.create_draft_order(items=[line], order_type="Take Away", customer_name=ctx["walk_in"],
			mode_of_payment=mode_of_payment, branch_name=branch_name, price_list=ctx["price_list"])
		name = res["invoice_name"]
		made_inv.append(name)
		if pay:
			P.pay_cash(name)
		return name

	def row_of(name):
		return frappe.db.get_value("POS Invoice Item", {"parent": name, "parenttype": "POS Invoice"},
			["options", "sugar_level", "ice_level"], as_dict=True)

	def detail_opts(name):
		return P.get_order_detail(name)["items"][0]["options"]

	def kitchen_opts(name):
		for o in P.get_kitchen_orders(status="Chưa làm", limit=500):
			if o["name"] == name:
				return o["items"][0]["options"]
		return "KHÔNG THẤY"

	def customer_opts(name):
		rows = frappe.get_all("POS Invoice", filters={"name": name},
			fields=["name", "docstatus", "creation", "custom_kitchen_status", "order_type", "rounded_total",
				"grand_total", "currency", "payment_code", "order_note"])
		return C._orders_payload(frappe._dict(display_name="ZZTEST"), rows)[0]["items"][0]["options"]

	def three_apis(name):
		return {"detail": detail_opts(name), "kitchen": kitchen_opts(name), "khách": customer_opts(name)}

	admin = frappe.session.user
	frappe.set_user("Administrator")
	try:
		# Khách TẠM (2026-11-24): đơn thử chọn khách rõ, không phụ thuộc Khách vãng lai của POS Profile thật.
		_wi = frappe.new_doc("Customer")
		_wi.customer_name = f"ZZTEST WI Legacy {frappe.generate_hash(length=6)}"
		_wi.customer_type = "Individual"
		_wi.customer_group = frappe.db.get_single_value("Selling Settings", "customer_group") or "Individual"
		_wi.territory = frappe.db.get_single_value("Selling Settings", "territory") or "All Territories"
		_wi.insert(ignore_permissions=True)
		ctx["walk_in"] = _wi.name
		print("== A. read_line_options ==")
		ok("A1 '[]' + 100/100 -> []", read_line_options("[]", "100", "100") == [])
		ok("A2 NULL + 70/50 -> Đường 70% · Đá 50%", labels(read_line_options(None, "70", "50")) == "Đường 70% · Đá 50%")
		ok("A3 '' + 70/50 -> dựng legacy", labels(read_line_options("", "70", "50")) == "Đường 70% · Đá 50%")
		js = json.dumps([{"group": "G", "group_title": "Đường", "value": "30%", "price": 0}], ensure_ascii=False)
		ok("A4 JSON có dữ liệu -> giữ JSON, bỏ cột cũ", labels(read_line_options(js, "100", "100")) == "Đường 30%")
		ok("A5 JSON hỏng -> []", read_line_options("{hỏng", "100", "100") == [])
		ok("A6 NULL + cột trống -> []", read_line_options(None, None, "") == [])

		print("== B. Default Custom Field (sau migrate) ==")
		meta = frappe.get_meta("POS Invoice Item")
		for f in ("sugar_level", "ice_level"):
			df = meta.get_field(f)
			ok(f"B {f}: không còn default", df is not None and not df.default, f"(default={getattr(df, 'default', None)!r})")
			ok(f"B {f}: lựa chọn đầu là trống (Frappe không tự gán '50')", df is not None and (df.options or "").startswith(chr(10)),
				f"(options={getattr(df, 'options', None)!r})")

		profile = P._get_pos_profile(branch_name)
		ctx["price_list"] = ctx["price_list"] or profile.get("selling_price_list")
		if not P._open_shift_of(profile.name):
			print(f"DỪNG: POS Profile {profile.name} chưa có ca đang mở.")
			return False
		groups = resolve_option_groups([item_plain, item_with_options])
		ok("Chuẩn bị: item_plain không có Option Group", not groups.get(item_plain), f"({[g['title'] for g in groups.get(item_plain, [])]})")
		ok("Chuẩn bị: item_with_options có Option Group", bool(groups.get(item_with_options)))

		print("== C. Món không Option Group ==")
		c = make(item_plain, [], pay=True)
		r = row_of(c)
		ok("C1 DB options '[]', cột cũ trống", r.options == "[]" and not r.sugar_level and not r.ice_level, f"({dict(r)})")
		got = three_apis(c)
		ok("C2 detail / kitchen / khách đều []", all(v == [] for v in got.values()), f"({got})")

		print("== D. Món có Option Group (giá trị mặc định) ==")
		chosen = []
		for g in groups.get(item_with_options, []):
			vals = [v["label"] for v in g["values"] if v.get("is_default")]
			if vals:
				chosen.append({"group": g["name"], "value": vals if g["selection_type"] == "Chọn nhiều" else vals[0]})
		d = make(item_with_options, chosen, pay=True)
		r = row_of(d)
		saved = json.loads(r.options or "[]")
		got = three_apis(d)
		ok("D1 options khớp JSON đã lưu ở cả 3 API", all(labels(v) == labels(read_line_options(r.options)) for v in got.values())
			and bool(saved) == bool(chosen), f"({labels(got['detail'])})")
		legacy_groups = [g for g in groups.get(item_with_options, []) if g.get("legacy_field")]
		for g in legacy_groups:
			ok(f"D2 nhóm '{g['title']}' có legacy_field -> ghi cột {g['legacy_field']}",
				bool(r.get(g["legacy_field"])) or not any(x["group"] == g["name"] for x in chosen),
				f"({g['legacy_field']}={r.get(g['legacy_field'])!r})")
		if not legacy_groups:
			print("INFO D2 SKIP: món không có nhóm legacy_field")

		print("== E. Đơn cũ giả lập (options NULL + 70/50) ==")
		e = make(item_plain, [], pay=True)
		frappe.db.set_value("POS Invoice Item", {"parent": e, "parenttype": "POS Invoice"},
			{"options": None, "sugar_level": "70", "ice_level": "50"}, update_modified=False)
		got = three_apis(e)
		ok("E1 cả 3 API dựng Đường 70% · Đá 50%", all(labels(v) == "Đường 70% · Đá 50%" for v in got.values()),
			f"({ {k: labels(v) for k, v in got.items()} })")

		print("== F. Request kiểu cũ (không khóa options) ==")
		f_ = make(item_plain, legacy_request=True)
		r = row_of(f_)
		ok("F1 cột cũ 70/50, options trống, hiển thị như trước",
			r.sugar_level == "70" and r.ice_level == "50" and not r.options and labels(detail_opts(f_)) == "Đường 70% · Đá 50%",
			f"({dict(r)})")

		print("== G. Báo cáo CHỈ ĐỌC: dòng options='[]' có cột cũ (đơn thật) ==")
		rows = frappe.db.sql("""
			select date_format(pi.creation, '%%Y-%%m') as month, pii.item_code, pi.docstatus, pi.status, count(*) as n
			from `tabPOS Invoice Item` pii join `tabPOS Invoice` pi on pi.name = pii.parent
			where pii.parenttype = 'POS Invoice' and pii.options = '[]'
				and (ifnull(pii.sugar_level, '') != '' or ifnull(pii.ice_level, '') != '')
				and pi.name not in %(made)s
			group by month, pii.item_code, pi.docstatus, pi.status
			order by month, pii.item_code""", {"made": made_inv or [""]}, as_dict=True)
		has_groups = resolve_option_groups(list({x.item_code for x in rows})) if rows else {}
		for x in rows:
			print(f"INFO {x.month} {x.item_code} docstatus={x.docstatus} {x.status}: {x.n} dòng"
				f" — món hiện {'CÓ' if has_groups.get(x.item_code) else 'KHÔNG có'} Option Group")
		if not rows:
			print("INFO không có dòng nào")
		print("INFO các dòng trên sẽ KHÔNG còn hiện đường/đá; không sửa dữ liệu.")
	except Exception:
		ok("Lỗi ngoài dự kiến", False)
		traceback.print_exc()
	finally:
		frappe.set_user("Administrator")
		frappe.db.rollback()
		left = [n for n in made_inv if frappe.db.exists("POS Invoice", n)]
		for n in left:
			try:
				doc = frappe.get_doc("POS Invoice", n)
				if doc.docstatus == 1:
					doc.cancel()
				frappe.delete_doc("POS Invoice", n, force=1, ignore_permissions=True)
			except Exception as ex:  # noqa: BLE001
				print(f"WARN không dọn được {n}: {ex} (hủy/xóa tay trên Desk)")
		if left:
			for lpe in frappe.get_all("Loyalty Point Entry", filters={"invoice": ["in", left]}, pluck="name"):
				frappe.delete_doc("Loyalty Point Entry", lpe, force=1, ignore_permissions=True)
			frappe.db.commit()
			print(f"WARN có commit ngầm, đã dọn {left}")
		else:
			print("Đã rollback: không còn đơn thử")
		_tmp = ctx.get("walk_in")
		if _tmp and frappe.db.exists("Customer", _tmp):
			try:
				frappe.delete_doc("Customer", _tmp, force=1, ignore_permissions=True)
				frappe.db.commit()
				print(f"WARN có commit ngầm, đã xóa khách tạm {_tmp}")
			except Exception as ex:  # noqa: BLE001
				print(f"WARN không xóa được khách tạm {_tmp}: {ex} (xóa tay trên Desk)")
		frappe.set_user(admin)

	failed = [c for c, passed in results if not passed]
	print("== KẾT QUẢ:", "PASS" if not failed else f"FAIL ({len(failed)})", f"— {len(results) - len(failed)}/{len(results)} ==")
	return not failed
