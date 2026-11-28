def check_everything(include_write=True, only=None):
	"""Chạy gộp mọi selfcheck MYPOS, in bảng PASS / FAIL / SKIP cuối cùng.

	    bench --site <site> execute mypos.selfcheck.check_everything.check_everything
	    bench --site <site> execute mypos.selfcheck.check_everything.check_everything --kwargs "{'include_write': False}"
	    bench --site <site> execute mypos.selfcheck.check_everything.check_everything --kwargs "{'only': ['table_card_check']}"

	Thứ tự: 1) prereq_check (điều kiện nền, chỉ đọc); 2) test CHỈ ĐỌC; 3) test GHI không cần dữ liệu quán (user tạm);
	4) test GHI cần dữ liệu quán — CHỈ khi prereq đạt, mỗi test tự dựng quán thử ZZTEST-* (test_shop.py) và tự dọn.
	Không dừng khi một test lỗi: bắt lỗi, in traceback ngắn, đi tiếp. Cuối cùng: zz_test_shop("list") để báo dữ liệu thử còn sót.
	Kết quả mỗi test đọc từ output của nó: có dòng bắt đầu bằng "FAIL" hoặc lỗi -> FAIL; có "PASS" / "OK" -> PASS;
	in "SKIP" mà không có PASS / FAIL -> SKIP. Trả về list {name, group, status, passes, fails, seconds, note}.
	"""
	import contextlib
	import importlib
	import io
	import re
	import sys
	import time
	import traceback

	import frappe

	READ_ONLY = [
		("apps_screen_check", "check_apps_screen"),
		("sidebar_check", "check_sidebar"),
		("desktop_icon_check", "check_desktop_icons"),
		("workspace_shortcut_check", "check_workspace_shortcuts"),
	]
	WRITE_NO_SHOP = [
		("apps_screen_roles_check", "check_apps_screen_roles"),
		("kitchen_desk_check", "check_kitchen_desk"),
	]
	WRITE_SHOP = [
		("branch_profile_check", "check_branch_profile"),
		("walk_in_customer_check", "check_walk_in_customer"),
		("payment_mode_check", "check_payment_modes"),
		("table_card_check", "check_table_card"),
		("draft_cancel_check", "check_draft_cancel"),
		("open_orders_check", "check_open_orders"),
		("shift_owner_check", "check_shift_owner"),
		("payment_status_check", "check_payment_status"),
		("sepay_hmac_check", "check_sepay_hmac"),
		("customer_display_check", "check_customer_display"),
		("order_status_check", "check_order_status"),
		("poll_load_check", "check_poll_load"),
		("orders_shift_check", "check_orders_shift"),
		("legacy_options_check", "check_legacy_options"),
		("surcharge_check", "check_option_surcharge"),
		("order_qr_selftest", "run_order_qr_selftest"),
		("order_history_selftest", "run_order_history_selftest"),
	]
	FAIL_RE = re.compile(r"^\s*FAIL\b", re.M)
	PASS_RE = re.compile(r"^\s*(?:PASS\b|OK\s)", re.M)
	SKIP_RE = re.compile(r"^\s*(?:SKIP\b|KẾT QUẢ: SKIP)", re.M)

	class Tee(io.TextIOBase):
		def __init__(self, *streams):
			self.streams = streams

		def write(self, s):
			for st in self.streams:
				st.write(s)
			return len(s)

		def flush(self):
			for st in self.streams:
				st.flush()

	rows = []

	def run_one(group, module, func, kwargs=None):
		if only and module not in only:
			return
		print(f"\n{'=' * 72}\n>>> {group}: mypos.selfcheck.{module}.{func}\n{'=' * 72}")
		buf = io.StringIO()
		started = time.time()
		note = ""
		error = False
		try:
			fn = getattr(importlib.import_module(f"mypos.selfcheck.{module}"), func)
			with contextlib.redirect_stdout(Tee(sys.stdout, buf)):
				fn(**(kwargs or {}))
		except Exception as e:  # noqa: BLE001
			error = True
			tb = traceback.format_exception(type(e), e, e.__traceback__)
			note = ("".join(tb[-2:]).strip().replace("\n", " | "))[:300]
			print(f"LỖI {module}: {note}")
		finally:
			try:
				frappe.db.rollback()
			except Exception:  # noqa: BLE001
				pass
			frappe.set_user("Administrator")
		text = buf.getvalue()
		fails, passes, skips = len(FAIL_RE.findall(text)), len(PASS_RE.findall(text)), len(SKIP_RE.findall(text))
		if error or fails:
			status = "FAIL"
		elif passes:
			status = "PASS"
		elif skips:
			status = "SKIP"
			m = re.search(r"^\s*SKIP:?\s*(.+)$", text, re.M)
			note = note or (m.group(1)[:160] if m else "")
		else:
			status = "FAIL"
			note = note or "không có dòng PASS / FAIL / SKIP nào"
		rows.append({"name": module, "group": group, "status": status, "passes": passes, "fails": fails,
			"seconds": round(time.time() - started, 1), "note": note})

	frappe.set_user("Administrator")
	pre = {"ok": False}
	print(f"{'=' * 72}\n>>> 0. Điều kiện nền: mypos.selfcheck.prereq_check.check_prereq\n{'=' * 72}")
	try:
		from mypos.selfcheck.prereq_check import check_prereq

		pre = check_prereq()
	except Exception as e:  # noqa: BLE001
		print(f"LỖI prereq_check: {e!r}")
	rows.append({"name": "prereq_check", "group": "0 điều kiện nền", "status": "PASS" if pre.get("ok") else "FAIL",
		"passes": 0, "fails": len(pre.get("missing") or []), "seconds": 0,
		"note": "; ".join(pre.get("missing") or [])[:160]})

	for module, func in READ_ONLY:
		run_one("1 chỉ đọc", module, func)
	if include_write:
		for module, func in WRITE_NO_SHOP:
			run_one("2 ghi (user tạm)", module, func)
		for module, func in WRITE_SHOP:
			if pre.get("ok"):
				run_one("3 ghi (quán thử)", module, func)
			elif not only or module in only:
				rows.append({"name": module, "group": "3 ghi (quán thử)", "status": "SKIP", "passes": 0, "fails": 0,
					"seconds": 0, "note": "thiếu điều kiện nền (xem prereq_check)"})

	print(f"\n{'=' * 72}\n>>> Dữ liệu thử còn sót\n{'=' * 72}")
	try:
		from mypos.selfcheck.test_shop import zz_test_shop

		zz_test_shop("list")
	except Exception as e:  # noqa: BLE001
		print(f"LỖI liệt kê dữ liệu thử: {e!r}")

	print(f"\n{'=' * 72}\nBẢNG KẾT QUẢ\n{'=' * 72}")
	print(f"{'Test':<28} {'Nhóm':<18} {'KQ':<5} {'PASS':>5} {'FAIL':>5} {'giây':>6}  Ghi chú")
	for r in rows:
		print(f"{r['name']:<28} {r['group']:<18} {r['status']:<5} {r['passes']:>5} {r['fails']:>5} {r['seconds']:>6}  {r['note']}")
	total = {s: sum(1 for r in rows if r["status"] == s) for s in ("PASS", "FAIL", "SKIP")}
	print(f"TỔNG: {len(rows)} test — PASS {total['PASS']}, FAIL {total['FAIL']}, SKIP {total['SKIP']}")
	return rows
