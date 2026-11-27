def check_order_status(pos_profile, item_code, mode_of_payment, price_list=None):
	"""Màn theo dõi đơn /pos/status (order_status_api.py, 2026-11-27).

	Dán CẢ hàm vào `bench --site <site> console` MỚI rồi gọi, ví dụ:
	    check_order_status("POS TEST", "<mã món VARIANT>", "Cash", price_list="<Price List của MYPOS Menu>")

	KHÔNG đụng ca / đơn / thẻ / khách thật: chép POS Profile thành 2 profile "ZZTEST Status ..." (A, K ở profile 1; B ở profile 2),
	user tạm A (POS CASHIER), K (POS KITCHEN), B (POS CASHIER, profile 2), M (POS MANAGER, không thuộc profile nào),
	X (POS KITCHEN, không thuộc profile nào); 1 thẻ bàn tạm; 2 Customer tạm (khách vãng lai + khách có tên đầy đủ).
	Cuối hàm (finally) dọn mọi dữ liệu thử; dòng KẾT QUẢ luôn được in.
	"""
	import json
	import time
	import traceback

	import frappe
	from frappe.utils import now_datetime, nowdate

	from mypos.mypos.api import order_status_api as S
	from mypos.mypos.api import pos_api as P

	PREFIX = "zz.test.status"
	PROFILE_PREFIX = "ZZTEST Status "
	CUSTOMER_PREFIX = "ZZTEST ST "
	CARD_PREFIX = "ZZS-"
	FULL_NAME = "Nguyễn Văn Thạch"  # khách có tên đầy đủ -> TV chỉ được hiện "Thạch"
	ROLE_OF = {"A": "POS CASHIER", "K": "POS KITCHEN", "B": "POS CASHIER", "M": "POS MANAGER", "X": "POS KITCHEN"}
	# Khóa được phép trong response (ngoài ra là lộ dữ liệu)
	BOARD_KEYS = {"profile", "v", "preparing", "ready", "more"}
	ENTRY_KEYS = {"code", "name", "label", "at", "items", "items_more"}
	ITEM_KEYS = {"name", "qty"}  # món: CHỈ tên + số lượng (2026-11-27)
	DEADLOCK = getattr(frappe, "QueryDeadlockError", None) or getattr(frappe.exceptions, "QueryDeadlockError", ())
	results, users, ctx = [], {}, {"profiles": []}

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
				for dt in ("POS Invoice", "POS Opening Entry"):
					for n in frappe.get_all(dt, filters={"pos_profile": prof}, pluck="name"):
						delete_fresh(dt, n, removed, failed, cancel=True)
				delete_fresh("POS Profile", prof, removed, failed)
			for card in frappe.get_all("MYPOS Buzzer", filters={"buzzer_number": ["like", CARD_PREFIX + "%"]}, pluck="name"):
				delete_fresh("MYPOS Buzzer", card, removed, failed)
			for c in frappe.get_all("Customer", filters={"customer_name": ["like", CUSTOMER_PREFIX + "%"]}, pluck="name"):
				for n in frappe.get_all("POS Invoice", filters={"customer": c}, pluck="name"):
					delete_fresh("POS Invoice", n, removed, failed, cancel=True)
				delete_fresh("Customer", c, removed, failed)
			contacts = set(frappe.get_all("Contact", filters={"user": ["like", PREFIX + ".%"]}, pluck="name"))
			contacts |= set(frappe.get_all("Contact", filters={"email_id": ["like", PREFIX + ".%"]}, pluck="name"))
			for c in sorted(contacts):
				delete_fresh("Contact", c, removed, failed)
			for u in frappe.get_all("User", filters={"name": ["like", PREFIX + ".%"]}, pluck="name"):
				frappe.clear_cache(user=u)
				for nl in frappe.get_all("Notification Log", filters={"for_user": u}, pluck="name"):
					delete_fresh("Notification Log", nl, removed, failed)
				delete_fresh("User", u, removed, failed)
			frappe.cache.delete_keys(S.STATUS_CACHE_PREFIX)
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
	def paid(order_type="Take Away", buzzer=None, customer=None, key="A", lines=None):
		line = lines or [{"item_code": item_code, "qty": 1, "options": []}]
		res, err = as_user(key, P.create_draft_order, line, order_type, customer_name=customer,
			mode_of_payment=mode_of_payment, price_list=ctx["price_list"], buzzer=buzzer)
		if err:
			raise err
		name = res["invoice_name"]
		_r, err = as_user(key, P.pay_cash, name)
		if err:
			raise err
		return name

	def board(key, pos_profile=None):
		return as_user(key, S.get_order_status_board, pos_profile)

	def find(b, code):
		"""(cột, dòng) của mã trong board, hoặc (None, None)."""
		for col in ("preparing", "ready"):
			for e in (b or {}).get(col, []):
				if e["code"] == code:
					return col, e
		return None, None

	admin = frappe.session.user
	frappe.set_user("Administrator")
	try:
		print("== 0. Dọn dữ liệu thử còn sót ==")
		removed0, failed0 = purge_leftovers()
		report_cleanup(removed0, failed0, "đầu")
		if failed0:
			raise RuntimeError("Còn dữ liệu thử của lần chạy trước không xóa được — xóa tay theo WARN rồi chạy lại.")

		print("== 1. Rút gọn tên (hàm thuần, server) ==")
		cases = [
			("Nguyễn Văn Thạch", "Thạch"),
			("Thạch", "Thạch"),
			("", ""),
			("   ", ""),
			(None, ""),
			("Lê Hoàng Nhật Quỳnh", "Quỳnh"),
			("Ánh.", "Ánh"),
			("Khách 0912345678", ""),
			("Tuấn 0912", ""),
			("Bartholomewabcdef", "Bartholomew…"),
		]
		for full, want in cases:
			got = S.short_call_name(full)
			ok(f"1 short_call_name({full!r}) = {want!r}", got == want, f"(được {got!r})")
		ok("1 Tên dài cắt đúng NAME_MAX ký tự", len(S.short_call_name("A" * 40)) == S.NAME_MAX)
		ok("1 Mã ngắn: ACC-PSINV-2026-00088 -> #00088", S.short_order_code("ACC-PSINV-2026-00088") == "#00088")
		ok("1 Số lượng 2.0 -> 2, 1.5 giữ nguyên", S._qty(2.0) == 2 and isinstance(S._qty(2.0), int) and S._qty(1.5) == 1.5)

		print("== 2. Dữ liệu tạm ==")
		src = frappe.get_doc("POS Profile", pos_profile)
		if not src.get("branch"):
			raise RuntimeError(f"POS Profile {pos_profile} chưa có Branch.")
		ctx["price_list"] = price_list or src.get("selling_price_list")
		modes = [p.mode_of_payment for p in (src.get("payments") or []) if p.mode_of_payment] or [mode_of_payment]

		def customer(name):
			c = frappe.new_doc("Customer")
			c.customer_name = name
			c.customer_type = "Individual"
			c.customer_group = frappe.db.get_single_value("Selling Settings", "customer_group") or "Individual"
			c.territory = frappe.db.get_single_value("Selling Settings", "territory") or "All Territories"
			c.insert(ignore_permissions=True)
			return c.name

		tag = frappe.generate_hash(length=4)
		wi = customer(f"{CUSTOMER_PREFIX}WI {tag}")
		named = customer(f"{CUSTOMER_PREFIX}{tag} {FULL_NAME}")
		for key, role in ROLE_OF.items():
			email = f"{PREFIX}.{key.lower()}@example.com"
			frappe.get_doc({"doctype": "User", "email": email, "first_name": f"ZZTEST {key}",
				"user_type": "System User", "send_welcome_email": 0, "enabled": 1,
				"roles": [{"role": role}]}).insert(ignore_permissions=True)
			users[key] = email

		def make_profile(members):
			prof = frappe.copy_doc(src)
			prof.set("__newname", f"{PROFILE_PREFIX}{frappe.generate_hash(length=6)}")
			prof.set("custom_walk_in_customer", wi)
			prof.disabled = 0
			prof.set("applicable_for_users", [])
			for key in members:
				prof.append("applicable_for_users", {"user": users[key], "default": 1})
			prof.flags.mypos_allow_shared_branch = True  # chỉ self-test (branch.md §2)
			prof.insert(ignore_permissions=True)
			ctx["profiles"].append(prof.name)
			return prof.name

		prof1 = make_profile(("A", "K"))
		prof2 = make_profile(("B",))

		def open_shift():
			doc = frappe.get_doc({"doctype": "POS Opening Entry", "pos_profile": prof1, "company": src.company,
				"user": users["A"], "period_start_date": now_datetime(), "posting_date": nowdate(),
				"balance_details": [{"mode_of_payment": m, "opening_amount": 0} for m in modes]})
			doc.insert(ignore_permissions=True)
			doc.submit()
			return doc.name

		_shift, err = as_user("A", open_shift)
		if err:
			raise err
		card = frappe.get_doc({"doctype": "MYPOS Buzzer", "buzzer_number": f"{CARD_PREFIX}{tag.upper()}",
			"branch": src.branch, "status": "Sẵn sàng"}).insert(ignore_permissions=True)
		card_no = card.buzzer_number
		frappe.db.commit()
		print(f"INFO profile {prof1} (A, K) / {prof2} (B), thẻ {card_no}")

		print("== 3. Đơn đi qua hai cột ==")
		t1 = paid("Take Away", customer=named)
		c1 = S.short_order_code(t1)
		b, err = board("K")
		col, row = find(b, c1)
		ok("3a Kitchen K (đúng profile): đơn Chưa làm ở cột trái", err is None and col == "preparing", f"({err or col})")
		ok("3b Tên gọi chỉ là từ cuối ('Thạch'), nhãn 'Mang đi'", row and row["name"] == "Thạch" and row["label"] == "Mang đi",
			f"({row})")
		item_name = frappe.db.get_value("Item", item_code, "item_name")
		ok("3b' Món: đúng 1 dòng {name: tên món, qty: 1}, items_more 0",
			row and row["items"] == [{"name": item_name, "qty": 1}] and row["items_more"] == 0, f"({row and row['items']})")
		_r, err = as_user("K", P.set_kitchen_status, t1, "Đã làm")
		col, row = find(board("A")[0], c1)
		ok("3c Đã làm -> sang cột phải (Cashier A thấy)", err is None and col == "ready", f"({err or col})")
		_r, err = as_user("A", P.set_kitchen_status, t1, "Đã hoàn thành")
		col, _row = find(board("K")[0], c1)
		ok("3d Đã hoàn thành -> biến mất", err is None and col is None, f"({err or col})")

		print("== 4. Thẻ bàn, khách vãng lai, thứ tự ==")
		d4 = paid("Dine In", buzzer=card.name)
		t4 = paid("Take Away")
		b = board("K")[0]
		_c, row = find(b, S.short_order_code(d4))
		ok("4a Dine In có thẻ -> nhãn 'Thẻ bàn <số>'", row and row["label"] == f"Thẻ bàn {card_no}", f"({row})")
		_c, row = find(b, S.short_order_code(t4))
		ok("4b Khách vãng lai -> name rỗng (chỉ hiện mã)", row is not None and row["name"] == "", f"({row})")
		codes = [e["code"] for e in b["preparing"]]
		ok("4c Cột trái cũ nhất ở trên (creation)",
			codes.index(S.short_order_code(d4)) < codes.index(S.short_order_code(t4)), f"({codes})")
		as_user("K", P.set_kitchen_status, t4, "Đã làm")
		time.sleep(1.1)  # kitchen_done_at khác nhau rõ ràng
		as_user("K", P.set_kitchen_status, d4, "Đã làm")
		ready = [e["code"] for e in board("K")[0]["ready"]]
		ok("4d Cột phải theo thời điểm 'Đã làm' (t4 bấm trước d4 -> t4 ở trên)",
			ready.index(S.short_order_code(t4)) < ready.index(S.short_order_code(d4)), f"({ready})")
		as_user("A", P.set_kitchen_status, t4, "Đã hoàn thành")
		as_user("A", P.set_kitchen_status, d4, "Đã hoàn thành")

		print("== 4b. Món: gộp cùng tên, giới hạn ITEM_LIMIT ==")
		m4 = paid("Take Away", lines=[{"item_code": item_code, "qty": 2, "options": []},
			{"item_code": item_code, "qty": 3, "options": []}])
		_c, row = find(board("K")[0], S.short_order_code(m4))
		ok("4e Hai dòng cùng món -> gộp 1 món qty 5", row and row["items"] == [{"name": item_name, "qty": 5}], f"({row and row['items']})")
		fake = [frappe._dict(parent="X", item_name=f"Món {i}", qty=1) for i in range(S.ITEM_LIMIT + 3)]
		orig = frappe.get_all
		try:
			frappe.get_all = lambda *a, **k: fake if a and a[0] == "POS Invoice Item" else orig(*a, **k)
			lines, hidden = S.items_by_invoice(["X"])["X"]
		finally:
			frappe.get_all = orig
		ok(f"4f {S.ITEM_LIMIT + 3} món khác tên -> trả {S.ITEM_LIMIT}, items_more 3", len(lines) == S.ITEM_LIMIT and hidden == 3,
			f"({len(lines)}, {hidden})")
		as_user("A", P.resolve_open_order, m4, "Khách không nhận", "dọn thử")

		print("== 5. Đơn kết thúc có lý do / hủy / Draft không hiện ==")
		f5 = paid("Take Away")
		as_user("A", P.resolve_open_order, f5, "Không thực hiện được", "Hết nguyên liệu")
		n5 = paid("Take Away")
		as_user("A", P.resolve_open_order, n5, "Khách không nhận", "Khách bỏ về")
		x5 = paid("Take Away")
		inv = frappe.get_doc("POS Invoice", x5)
		inv.flags.ignore_permissions = True
		inv.cancel()
		line = [{"item_code": item_code, "qty": 1, "options": []}]
		dr = as_user("A", P.create_draft_order, line, "Take Away", mode_of_payment=mode_of_payment,
			price_list=ctx["price_list"])[0]["invoice_name"]
		b = board("K")[0]
		for label, name in (("Không thực hiện được", f5), ("Khách không nhận", n5), ("Hủy (docstatus 2)", x5), ("Draft chưa thanh toán", dr)):
			ok(f"5 {label} không hiện", find(b, S.short_order_code(name))[0] is None)
		as_user("A", P.cancel_draft_order, dr, 0, "Khách đổi ý")

		print("== 6. Quyền theo POS Profile ==")
		p6 = paid("Take Away")
		code6 = S.short_order_code(p6)
		b, err = board("B")
		ok("6a Cashier B (profile 2) không thấy đơn profile 1", err is None and find(b, code6)[0] is None
			and b["profile"] == prof2, f"({err or b['profile']})")
		b, err = board("B", prof1)
		ok("6b B gửi pos_profile của profile 1 -> server bỏ qua, vẫn profile 2", err is None and b["profile"] == prof2
			and find(b, code6)[0] is None, f"({err or b['profile']})")
		_r, err = board("X")
		ok("6c Kitchen không thuộc profile nào -> lỗi 'chưa thuộc POS Profile'",
			err is not None and "chưa thuộc pos profile" in str(err).lower(), f"({err})")
		b, err = board("M", prof1)
		ok("6d Manager chọn profile 1 -> thấy đơn", err is None and find(b, code6)[0] == "preparing", f"({err})")
		cfg, err = as_user("M", S.get_order_status_config, prof1)
		ok("6e Config của Manager có danh sách profile (gồm profile 1), brand chỉ name + logo",
			err is None and prof1 in cfg["profiles"] and set(cfg["brand"]) == {"name", "logo"}, f"({err or cfg})")
		cfg, err = as_user("K", S.get_order_status_config)
		ok("6f Config của Kitchen: không có danh sách profile", err is None and cfg["profiles"] == [] and cfg["profile"] == prof1,
			f"({err or cfg})")
		ch, err = as_user("K", S.get_order_status_changes)
		ok("6g get_order_status_changes trả {profile, v} của profile 1", err is None and ch["profile"] == prof1 and ch["v"],
			f"({err or ch})")
		_r, err = board("M", "ZZTEST khong ton tai")
		ok("6h Manager chọn profile không tồn tại -> lỗi", err is not None)

		print("== 7. Response không chứa dữ liệu nhạy cảm ==")
		as_user("K", P.set_kitchen_status, p6, "Đã làm")
		t7 = paid("Take Away", customer=named)
		b = board("K")[0]
		ok("7a Khóa gốc chỉ gồm profile / v / preparing / ready / more", set(b) == BOARD_KEYS, f"({sorted(b)})")
		bad = [e for e in b["preparing"] + b["ready"] if set(e) != ENTRY_KEYS]
		ok("7b Mỗi dòng chỉ có code / name / label / at / items / items_more", not bad, f"({bad[:2]})")
		bad_items = [it for e in b["preparing"] + b["ready"] for it in e["items"] if set(it) != ITEM_KEYS]
		ok("7b' Mỗi món chỉ có name + qty (không giá, tùy chọn, ghi chú, item_code)", not bad_items, f"({bad_items[:2]})")
		text = json.dumps(b, ensure_ascii=False, default=str)
		ok("7c Không có tên đầy đủ, mã Customer, tên hóa đơn đầy đủ",
			FULL_NAME not in text and named not in text and p6 not in text and t7 not in text, "")
		rate = frappe.db.get_value("POS Invoice", t7, "grand_total")
		ok("7c' Không có khóa tiền / giá / ghi chú / tùy chọn",
			not any(k in text for k in ('"rate"', '"amount"', '"grand_total"', '"order_note"', '"options"', '"price"', '"mobile'))
			and (not rate or f'"{rate}"' not in text), "")
		mobile = frappe.db.get_value("Customer", named, "mobile_no") or ""
		ok("7d Không có SĐT khách", not mobile or mobile not in text)
		as_user("A", P.set_kitchen_status, p6, "Đã hoàn thành")
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
				+ frappe.get_all("Customer", filters={"customer_name": ["like", CUSTOMER_PREFIX + "%"]}, pluck="name") \
				+ frappe.get_all("MYPOS Buzzer", filters={"buzzer_number": ["like", CARD_PREFIX + "%"]}, pluck="name") \
				+ frappe.get_all("POS Invoice", filters={"pos_profile": ["in", ctx["profiles"] or [""]]}, pluck="name")
			ok("8 Dọn dữ liệu: không còn profile / user / khách / thẻ / đơn thử", not left, f"({left})")
		except Exception:  # noqa: BLE001
			ok("8 Dọn dữ liệu (lỗi khi dọn — xem WARN / traceback)", False)
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
