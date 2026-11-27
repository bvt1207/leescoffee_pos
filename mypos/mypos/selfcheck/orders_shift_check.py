def check_orders_shift(item_code, mode_of_payment, branch_name=None, price_list=None, customer=None, cleanup=True):
	"""Màn Orders: "Ca hiện tại" + "Lịch sử" (get_orders / get_orders_summary) và phân quyền.

	Dán CẢ hàm vào `bench --site <site> console` rồi gọi, ví dụ:
	    check_orders_shift("<mã món>", "Tiền mặt", branch_name="<tên Branch>")

	Cần: Administrator có ca POS đang mở (POS Opening Entry Open) cho POS Profile của chi nhánh — script
	KHÔNG mở ca. item_code có giá trong price_list (bỏ trống = selling_price_list của POS Profile; nên truyền
	đúng Price List của MYPOS Menu đang bán). Tạo 5 đơn thử (Take Away), đổi
	posting_date/status bằng db.set_value để giả đơn ca trước / hôm qua (Consolidated giả) / 8 ngày trước,
	và 3 user tạm (mỗi người 1 role POS). Không commit: cuối hàm ROLLBACK; nếu có commit ngầm thì tự
	trả status, hủy + xóa đơn, Loyalty Point Entry, user tạm và in WARN.
	Sau khi PASS: chạy lại run_order_qr_selftest() và run_order_history_selftest() (file riêng trong .claude/docs/).
	Khách vãng lai (2026-11-24): đơn thử dùng Customer TẠM "ZZTEST WI ..." do script tự tạo và tự xóa — không cần POS Profile
	thật đã cấu hình Khách vãng lai, không dùng Customer thật nào.
	"""
	import traceback

	import frappe
	from frappe.utils import add_days, get_datetime, getdate, nowdate

	from mypos.mypos.api import pos_api as P
	from mypos.mypos.doctype.branch_config.branch_config import resolve_pos_profile_name

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

	ROLES = ("POS CASHIER", "POS KITCHEN", "POS MANAGER")
	results, made_inv, users = [], [], {}
	ctx = {"price_list": price_list, "walk_in": None}

	def ok(case, cond, extra=""):
		results.append((case, bool(cond)))
		print(f"{'PASS' if cond else 'FAIL'} {case} {extra}")

	def err_of(fn, *args, **kw):
		"""-> (tên lỗi | None, thông báo)."""
		try:
			fn(*args, **kw)
			return None, ""
		except Exception as e:  # noqa: BLE001
			frappe.clear_messages()
			return type(e).__name__, str(e)

	def names(rows):
		return {r["name"] for r in rows}

	def make(pay=False):
		res = P.create_draft_order(
			items=[{"item_code": item_code, "qty": 1, "options": []}],
			order_type="Take Away",
			customer_name=customer or ctx["walk_in"],
			mode_of_payment=mode_of_payment,
			branch_name=branch_name,
			price_list=ctx["price_list"],
		)
		name = res["invoice_name"]
		made_inv.append(name)
		if pay:
			P.pay_cash(name)
		return name

	def move(name, posting_date, posting_time="10:00:00", status=None):
		values = {"posting_date": posting_date, "posting_time": posting_time}
		if status:
			values["status"] = status
		frappe.db.set_value("POS Invoice", name, values, update_modified=False)

	admin = frappe.session.user
	frappe.set_user("Administrator")
	try:
		if not customer:
			# Khách TẠM (2026-11-24): đơn thử chọn khách rõ, không phụ thuộc Khách vãng lai của POS Profile thật.
			_wi = frappe.new_doc("Customer")
			_wi.customer_name = f"ZZTEST WI Orders {frappe.generate_hash(length=6)}"
			_wi.customer_type = "Individual"
			_wi.customer_group = frappe.db.get_single_value("Selling Settings", "customer_group") or "Individual"
			_wi.territory = frappe.db.get_single_value("Selling Settings", "territory") or "All Territories"
			_wi.insert(ignore_permissions=True)
			ctx["walk_in"] = _wi.name
		profile = P._get_pos_profile(branch_name)
		resolved = resolve_pos_profile_name()
		if resolved != profile.name:
			print(f"DỪNG: POS Profile của Administrator là {resolved}, không phải {profile.name} — get_orders lọc theo {resolved}.")
			return False
		shift = P._open_shift_of(profile.name)
		if not shift:
			print(f"DỪNG: POS Profile {profile.name} chưa có ca đang mở. Mở ca (POS Opening Entry) rồi chạy lại.")
			return False
		ctx["price_list"] = ctx["price_list"] or profile.get("selling_price_list")
		if not ctx["price_list"]:
			print("DỪNG: chưa có Price List — truyền price_list=\"<Price List của MYPOS Menu>\".")
			return False
		print(f"INFO POS Profile {profile.name}, ca {shift.name} mở lúc {shift.period_start_date}, Price List {ctx['price_list']}")

		today = getdate(nowdate())
		yesterday = add_days(today, -1)
		d8 = add_days(today, -8)
		start_day = getdate(get_datetime(shift.period_start_date))

		print("== 1. Tạo dữ liệu thử ==")
		a = make()                      # Draft trong ca
		b = make(pay=True)              # Paid trong ca
		c = make()                      # Draft ca trước
		move(c, add_days(start_day, -1))
		d = make(pay=True)              # Paid hôm qua, giả Consolidated (đã đóng ca)
		move(d, yesterday, status="Consolidated")
		e = make(pay=True)              # Paid 8 ngày trước
		move(e, d8)
		print(f"INFO A Draft={a}, B Paid={b}, C Draft ca trước={c}, D Consolidated hôm qua={d}, E 8 ngày={e}")

		print("== 2. Ca hiện tại ==")
		drafts = P.get_orders(status="draft", limit=200)
		paid = P.get_orders(status="paid", limit=200)
		ok("2a Draft trong ca có A, không có C", a in names(drafts) and c not in names(drafts))
		ok("2b Paid trong ca có B, không có D/E", b in names(paid) and not ({d, e} & names(paid)))
		ok("2c Mọi đơn trong ca có posting >= giờ mở ca",
			all(get_datetime(f"{v.posting_date} {v.posting_time}") >= get_datetime(shift.period_start_date)
				for v in frappe.get_all("POS Invoice", filters={"name": ["in", list(names(drafts) | names(paid)) or [""]]},
					fields=["posting_date", "posting_time"])))
		s = P.get_orders_summary()
		ok("2d COUNT khớp số dòng (Draft/Paid)",
			s["counts"]["draft"] == len(drafts) and s["counts"]["paid"] == len(paid) or len(paid) >= 200,
			f"(counts {s['counts']}, dòng {len(drafts)}/{len(paid)})")
		ok("2e old_drafts >= 1 (C) cho MANAGER", s["old_drafts"] >= 1, f"(old_drafts {s['old_drafts']})")
		ok("2f summary.shift = ca đang mở", (s["shift"] or {}).get("name") == shift.name)
		ok("2g Tìm mã ngắn A trong ca", a in names(P.get_orders(status="draft", search="#" + a.split("-")[-1])))
		ok("2h Không có đơn trả hàng", not any(
			frappe.db.get_value("POS Invoice", n, "is_return") for n in names(drafts) | names(paid)))

		print("== 3. Lịch sử (MANAGER) ==")
		hy = P.get_orders(scope="history", from_date=str(yesterday), to_date=str(yesterday), limit=200)
		ok("3a Hôm qua có D (Consolidated), không có A/B/C/E", d in names(hy) and not ({a, b, c, e} & names(hy)))
		sy = P.get_orders_summary(scope="history", from_date=str(yesterday), to_date=str(yesterday))
		ok("3b COUNT Hôm qua khớp", sy["counts"]["paid"] == len(hy) or len(hy) >= 200, f"({sy['counts']['paid']}/{len(hy)})")
		h7 = P.get_orders(scope="history", from_date=str(add_days(today, -6)), to_date=str(today), limit=200)
		ok("3c 7 ngày có B + D, không có E và Draft A/C", {b, d} <= names(h7) and not ({a, c, e} & names(h7)))
		h8 = P.get_orders(scope="history", from_date=str(d8), to_date=str(d8), search="#" + e.split("-")[-1])
		ok("3d Chọn ngày 8 ngày trước + tìm mã ngắn ra E", e in names(h8))
		hd = P.get_orders(scope="history")
		ok("3e Mặc định Lịch sử = hôm qua", d in names(hd) and b not in names(hd))
		ok("3f Đơn Consolidated trả status Consolidated", any(r["name"] == d and r["status"] == "Consolidated" for r in hy))
		if len(h7) >= 2:
			p1 = P.get_orders(scope="history", from_date=str(add_days(today, -6)), to_date=str(today), limit=1, start=0)
			p2 = P.get_orders(scope="history", from_date=str(add_days(today, -6)), to_date=str(today), limit=1, start=1)
			ok("3g Phân trang (start) không trùng, đúng thứ tự", p1 and p2 and p1[0]["name"] == h7[0]["name"]
				and p2[0]["name"] == h7[1]["name"])
		err, msg = err_of(P.get_orders, scope="history", from_date=str(today), to_date=str(yesterday))
		ok("3h from > to -> lỗi", err is not None and err != "PermissionError", f"({err}: {msg[:70]})")
		err, msg = err_of(P.get_orders, scope="history", from_date=str(add_days(today, -40)), to_date=str(today))
		ok("3i Khoảng > 31 ngày -> lỗi", err is not None and err != "PermissionError", f"({err}: {msg[:70]})")
		err, msg = err_of(P.get_orders, scope="abc")
		ok("3j scope lạ -> lỗi", err is not None, f"({err})")

		print("== 4. Phân quyền theo role (user tạm) ==")
		for role in ROLES:
			email = f"zz.test.orders.{role.split()[1].lower()}@example.com"
			if frappe.db.exists("User", email):
				frappe.delete_doc("User", email, force=1, ignore_permissions=True)
			frappe.get_doc({
				"doctype": "User", "email": email, "first_name": f"ZZTEST {role}",
				"user_type": "System User", "send_welcome_email": 0, "enabled": 1,
				"roles": [{"role": role}],
			}).insert(ignore_permissions=True)
			users[role] = email
		# Lỗi khác PermissionError (vd. không xác định được POS Profile của user tạm) = đã QUA kiểm tra quyền.
		expect = {
			"POS CASHIER": {"shift": False, "history": True},
			"POS MANAGER": {"shift": False, "history": False},
			"POS KITCHEN": {"shift": True, "history": True},
		}
		for role, exp in expect.items():
			frappe.set_user(users[role])
			try:
				for scope, blocked in exp.items():
					for fn in (P.get_orders, P.get_orders_summary):
						err, msg = err_of(fn, scope=scope)
						got = err == "PermissionError"
						ok(f"4 {role.split()[1]} {fn.__name__}({scope}) {'bị chặn' if blocked else 'được phép'}",
							got == blocked, f"({err}: {msg[:60]})" if err else "")
			finally:
				frappe.set_user("Administrator")
	except Exception:
		ok("Lỗi ngoài dự kiến", False)
		traceback.print_exc()
	finally:
		frappe.set_user("Administrator")
		frappe.db.rollback()
		for u in users.values():
			frappe.clear_cache(user=u)
		if cleanup:
			left_inv = [n for n in made_inv if frappe.db.exists("POS Invoice", n)]
			for n in left_inv:
				try:
					def _drop(n=n):
						if frappe.db.get_value("POS Invoice", n, "status") == "Consolidated":
							frappe.db.set_value("POS Invoice", n, "status", "Paid", update_modified=False)
						doc = frappe.get_doc("POS Invoice", n)
						if doc.docstatus == 1:
							doc.cancel()
						frappe.delete_doc("POS Invoice", n, force=1, ignore_permissions=True)

					retry_deadlock(_drop)
				except Exception as ex:  # noqa: BLE001
					print(f"WARN không dọn được {n}: {ex} (hủy/xóa tay trên Desk)")
			if left_inv:
				for lpe in frappe.get_all("Loyalty Point Entry", filters={"invoice": ["in", left_inv]}, pluck="name"):
					retry_deadlock(frappe.delete_doc, "Loyalty Point Entry", lpe, force=1, ignore_permissions=True)
			left_users = [u for u in users.values() if frappe.db.exists("User", u)]
			for u in left_users:
				retry_deadlock(frappe.delete_doc, "User", u, force=1, ignore_permissions=True)
			if left_inv or left_users:
				frappe.db.commit()
				print(f"WARN có commit ngầm, đã dọn đơn {left_inv} và user {left_users}")
			else:
				print("Đã rollback: không còn đơn / user thử")
			_tmp = ctx.get("walk_in")
			if _tmp and frappe.db.exists("Customer", _tmp):
				try:
					retry_deadlock(frappe.delete_doc, "Customer", _tmp, force=1, ignore_permissions=True)
					frappe.db.commit()
					print(f"WARN có commit ngầm, đã xóa khách tạm {_tmp}")
				except Exception as ex:  # noqa: BLE001
					print(f"WARN không xóa được khách tạm {_tmp}: {ex} (xóa tay trên Desk)")
		frappe.set_user(admin)

	failed = [c for c, passed in results if not passed]
	print("== KẾT QUẢ:", "PASS" if not failed else f"FAIL ({len(failed)})", f"— {len(results) - len(failed)}/{len(results)} ==")
	return not failed
