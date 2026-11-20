def check_shift_owner(pos_profile, item_code, mode_of_payment, price_list=None):
	"""Mở / đóng ca: chỉ ca của chính mình; MANAGER thao tác thay (pos_shift_hooks.py) + quyền Only If Creator.

	Dán CẢ hàm vào `bench --site <site> console` (SAU khi migrate) rồi gọi, ví dụ:
	    check_shift_owner("<POS Profile thật>", "CH-CFLON", "Cash", price_list="<Price List của MYPOS Menu>")

	KHÔNG đụng ca thật: chép POS Profile thành profile tạm "ZZTEST Shift ..." (Applicable for Users = user tạm),
	tạo user tạm A, B (POS CASHIER, trong danh sách), OUT (POS CASHIER, ngoài danh sách), K (POS KITCHEN), M (POS MANAGER).
	Ghi dữ liệu bằng ignore_permissions=True để kiểm riêng quy tắc của hook (quyền DocType kiểm ở mục 7).
	Đầu và cuối hàm xóa mọi POS Profile "ZZTEST Shift ..." + user zz.test.shift.* còn sót (kèm ca / phiếu đóng ca / đơn
	của profile tạm). Profile tạm: Applicable for Users = A, B, M với default = 0 (tránh validate_default_profile của ERPNext).
	Cuối hàm ROLLBACK; nếu có commit ngầm thì tự dọn và in WARN; mục 9 kiểm tra DB không còn dữ liệu thử.
	Sau khi PASS: chạy lại run_order_qr_selftest() và run_order_history_selftest().
	"""
	import traceback

	import frappe
	from frappe.utils import now_datetime, nowdate

	from leescoffee_pos.leescoffee_pos.api import customer_order_api as C
	from leescoffee_pos.leescoffee_pos.api import pos_api as P

	PREFIX = "zz.test.shift"
	PROFILE_PREFIX = "ZZTEST Shift "
	ROLE_OF = {"A": "POS CASHIER", "B": "POS CASHIER", "OUT": "POS CASHIER", "K": "POS KITCHEN", "M": "POS MANAGER"}
	results, users, made = [], {}, {"profile": None, "openings": [], "closings": [], "invoices": []}

	def ok(case, cond, extra=""):
		results.append((case, bool(cond)))
		print(f"{'PASS' if cond else 'FAIL'} {case} {extra}")

	def as_user(key, fn, *args, **kw):
		"""-> (kết quả | None, lỗi | None) khi chạy dưới user tạm `key`."""
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
			f"-> {type(err).__name__}: {str(err)[:110]}" if err else "-> KHÔNG bị chặn")

	def open_shift(cashier_key):
		doc = frappe.get_doc({
			"doctype": "POS Opening Entry",
			"pos_profile": made["profile"],
			"company": company,
			"user": users[cashier_key],
			"period_start_date": now_datetime(),
			"posting_date": nowdate(),
			# Bảng "Opening Balance Details" bắt buộc (reqd) trong ERPNext v16.
			"balance_details": [{"mode_of_payment": m, "opening_amount": 0} for m in balance_modes],
		})
		doc.insert(ignore_permissions=True)
		made["openings"].append(doc.name)
		doc.submit()
		return doc

	def close_shift(opening_name):
		from erpnext.accounts.doctype.pos_closing_entry.pos_closing_entry import make_closing_entry_from_opening

		closing = make_closing_entry_from_opening(frappe.get_doc("POS Opening Entry", opening_name))
		closing.insert(ignore_permissions=True)
		made["closings"].append(closing.name)
		closing.submit()
		return closing

	def purge_leftovers():
		"""Xóa mọi POS Profile "ZZTEST Shift ..." (kèm phiếu đóng ca, đơn, ca của nó) và user tạm còn trong DB
		(do lần chạy trước có commit ngầm). Chỉ đụng dữ liệu thử có tiền tố. Trả danh sách đã xóa (đã commit)."""
		removed = []
		for prof_name in frappe.get_all("POS Profile", filters={"name": ["like", PROFILE_PREFIX + "%"]}, pluck="name"):
			for dt in ("POS Closing Entry", "POS Invoice", "POS Opening Entry"):
				for n in frappe.get_all(dt, filters={"pos_profile": prof_name}, pluck="name"):
					try:
						doc = frappe.get_doc(dt, n)
						if doc.docstatus == 1:
							doc.flags.ignore_permissions = True
							doc.cancel()
						frappe.delete_doc(dt, n, force=1, ignore_permissions=True)
						removed.append(f"{dt} {n}")
					except Exception as ex:  # noqa: BLE001
						print(f"WARN không dọn được {dt} {n}: {ex} (xóa tay trên Desk)")
			try:
				frappe.delete_doc("POS Profile", prof_name, force=1, ignore_permissions=True)
				removed.append(f"POS Profile {prof_name}")
			except Exception as ex:  # noqa: BLE001
				print(f"WARN không xóa được POS Profile {prof_name}: {ex}")
		for u in frappe.get_all("User", filters={"name": ["like", PREFIX + ".%"]}, pluck="name"):
			frappe.delete_doc("User", u, force=1, ignore_permissions=True)
			removed.append(f"User {u}")
		if removed:
			frappe.db.commit()
		return removed

	def comments(doctype, name):
		return frappe.get_all("Comment", filters={"reference_doctype": doctype, "reference_name": name,
			"comment_type": "Info"}, pluck="content")

	admin = frappe.session.user
	frappe.set_user("Administrator")
	try:
		src = frappe.get_doc("POS Profile", pos_profile)
		company = src.company
		price_list = price_list or src.get("selling_price_list")
		balance_modes = [p.mode_of_payment for p in (src.get("payments") or []) if p.mode_of_payment] or [mode_of_payment]

		print("== 0. Dọn dữ liệu thử còn sót từ lần chạy trước ==")
		purge_leftovers()

		print("== 1. Dữ liệu tạm ==")
		for key, role in ROLE_OF.items():
			email = f"{PREFIX}.{key.lower()}@example.com"
			if frappe.db.exists("User", email):
				frappe.delete_doc("User", email, force=1, ignore_permissions=True)
			frappe.get_doc({"doctype": "User", "email": email, "first_name": f"ZZTEST {key}",
				"user_type": "System User", "send_welcome_email": 0, "enabled": 1,
				"roles": [{"role": role}]}).insert(ignore_permissions=True)
			users[key] = email
		prof = frappe.copy_doc(src)
		prof.set("__newname", f"{PROFILE_PREFIX}{frappe.generate_hash(length=6)}")
		prof.disabled = 0
		# copy_doc kéo theo dòng Applicable for Users của profile thật -> xóa hết rồi thêm user tạm.
		# default = 0: validate_default_profile của ERPNext chặn khi user đã là default ở profile khác.
		prof.set("applicable_for_users", [])
		for key in ("A", "B", "M"):
			prof.append("applicable_for_users", {"user": users[key], "default": 0})
		prof.insert(ignore_permissions=True)
		made["profile"] = prof.name
		print(f"INFO profile tạm {prof.name} (chép từ {pos_profile}); user {users}")

		print("== 2. Mở ca ==")
		_r, err = as_user("A", open_shift, "B")
		blocked("2a A mở ca tên B -> chặn", err, "chỉ được mở ca cho chính mình")
		_r, err = as_user("OUT", open_shift, "OUT")
		blocked("2b OUT (ngoài Applicable for Users) mở ca mình -> chặn", err, "không thuộc Applicable for Users")
		_r, err = as_user("K", open_shift, "K")
		blocked("2c KITCHEN mở ca -> chặn", err, "không có quyền mở/đóng ca")
		shift_a, err = as_user("A", open_shift, "A")
		ok("2d A mở ca của mình -> OK", err is None and shift_a and shift_a.status == "Open", f"({err})" if err else "")
		if not shift_a:
			raise RuntimeError("Không mở được ca A — dừng.")
		ok("2e Mở ca của chính mình: không có comment thay", not comments("POS Opening Entry", shift_a.name))
		_r, err = as_user("B", open_shift, "B")
		blocked("2f B mở khi ca A chưa đóng -> chặn, nêu tên A", err, "ca của zztest a")

		print("== 3. Bán hàng khi ca đang mở ==")
		n_open = frappe.db.count("POS Opening Entry", {"pos_profile": prof.name})
		line = [{"item_code": item_code, "qty": 1, "options": []}]
		res, err = as_user("A", P.create_draft_order, line, "Take Away", mode_of_payment=mode_of_payment, price_list=price_list)
		ok("3a create_draft_order dưới A -> OK", err is None and res, f"({type(err).__name__}: {str(err)[:100]})" if err else "")
		if res:
			made["invoices"].append(res["invoice_name"])

		def qr_like():
			with C._as_user(users["A"]):
				return P.create_draft_order(line, "Take Away", mode_of_payment=mode_of_payment, price_list=price_list)

		res2, err = as_user("M", qr_like)
		ok("3b Kiểu QR (_as_user Cashier của ca) -> OK", err is None and res2, f"({type(err).__name__}: {str(err)[:100]})" if err else "")
		if res2:
			made["invoices"].append(res2["invoice_name"])
		ok("3c Không tạo thêm ca mới", frappe.db.count("POS Opening Entry", {"pos_profile": prof.name}) == n_open)
		_r, err = as_user("B", P.create_draft_order, line, "Take Away", mode_of_payment=mode_of_payment, price_list=price_list)
		blocked("3d B tạo đơn khi ca A mở -> báo rõ lý do", err, "chưa đóng")

		print("== 4. Đóng ca ==")
		_r, err = as_user("B", close_shift, shift_a.name)
		blocked("4a B đóng ca của A -> chặn", err, "chỉ được đóng ca của chính mình")
		closing, err = as_user("M", close_shift, shift_a.name)
		ok("4b MANAGER đóng thay ca A -> OK", err is None and closing, f"({type(err).__name__}: {str(err)[:100]})" if err else "")
		if closing:
			ok("4c Comment 'Đóng ca thay' trên phiếu đóng ca + ca", any("Đóng ca thay" in c for c in comments("POS Closing Entry", closing.name))
				and any("Đóng ca thay" in c for c in comments("POS Opening Entry", shift_a.name)))
			ok("4d Cashier phiếu đóng ca vẫn là A", closing.user == users["A"])

		print("== 5. MANAGER mở thay ==")
		_r, err = as_user("M", open_shift, "OUT")
		blocked("5a MANAGER mở thay cho OUT (ngoài danh sách) -> chặn", err, "không thuộc Applicable for Users")
		shift_b, err = as_user("M", open_shift, "B")
		ok("5b MANAGER mở thay cho B -> OK", err is None and shift_b, f"({type(err).__name__}: {str(err)[:100]})" if err else "")
		if shift_b:
			ok("5c Comment 'Mở ca thay' trên ca B", any("Mở ca thay" in c for c in comments("POS Opening Entry", shift_b.name)))
			_r, err = as_user("A", close_shift, shift_b.name)
			blocked("6a A đóng ca của B -> chặn", err, "chỉ được đóng ca của chính mình")
			_r, err = as_user("K", close_shift, shift_b.name)
			blocked("6b KITCHEN đóng ca -> chặn", err, "không có quyền mở/đóng ca")

		print("== 7. Quyền Only If Creator (sau migrate) ==")
		for dt in ("POS Opening Entry", "POS Closing Entry"):
			rows = frappe.get_all("Custom DocPerm", filters={"parent": dt, "role": "POS CASHIER", "permlevel": 0},
				fields=["name", "if_owner", "read", "create", "submit"])
			ok(f"7 {dt}: CASHIER đúng 1 dòng, if_owner = 1, giữ read/create/submit",
				len(rows) == 1 and rows[0].if_owner and rows[0].read and rows[0].create and rows[0].submit, f"({rows})")
			mgr = frappe.get_all("Custom DocPerm", filters={"parent": dt, "role": "POS MANAGER", "permlevel": 0},
				fields=["if_owner"])
			ok(f"7 {dt}: MANAGER không bị Only If Creator", len(mgr) == 1 and not mgr[0].if_owner, f"({mgr})")
	except Exception:
		ok("Lỗi ngoài dự kiến", False)
		traceback.print_exc()
	finally:
		frappe.set_user("Administrator")
		frappe.db.rollback()
		for u in users.values():
			frappe.clear_cache(user=u)
		removed = purge_leftovers()
		if removed:
			print(f"WARN có commit ngầm, đã dọn: {removed}")
		else:
			print("Đã rollback: không còn dữ liệu thử")
		left_profiles = frappe.get_all("POS Profile", filters={"name": ["like", PROFILE_PREFIX + "%"]}, pluck="name")
		left_users = frappe.get_all("User", filters={"name": ["like", PREFIX + ".%"]}, pluck="name")
		ok("9 Dọn dữ liệu: không còn POS Profile ZZTEST Shift / user tạm trong DB", not left_profiles and not left_users,
			f"(profile {left_profiles}, user {left_users})")
		frappe.set_user(admin)

	failed = [c for c, passed in results if not passed]
	print("== KẾT QUẢ:", "PASS" if not failed else f"FAIL ({len(failed)})", f"— {len(results) - len(failed)}/{len(results)} ==")
	return not failed
