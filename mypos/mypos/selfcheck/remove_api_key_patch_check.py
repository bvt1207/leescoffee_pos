def check_remove_api_key_patch():
	"""Patch mypos.patches.v1_remove_sepay_api_key (xóa field Branch.sepay_api_key, 2026-11-28).

	    bench --site <site> execute mypos.selfcheck.remove_api_key_patch_check.check_remove_api_key_patch

	  P1 Sau migrate: không còn Custom Field "Branch-sepay_api_key", cột `tabBranch.sepay_api_key`, dòng `__Auth` của field;
	     fixture không còn field (nạp lại fixture không tạo lại).
	  P2 Chạy lại patch trên site sạch -> không lỗi, không làm gì (idempotent).
	  P3 Giả lập site cũ: tạo lại Custom Field + Branch thử "ZZTEST-PATCH-*" có giá trị key cũ (và secret HMAC) -> chạy patch ->
	     field, cột, giá trị `__Auth` của key cũ bị xóa; Branch còn nguyên, secret HMAC còn nguyên.
	Dọn (finally): xóa Branch thử, chạy lại patch (gỡ field nếu P3 dừng giữa chừng). Tạo / xóa cột là DDL (tự commit).
	"""
	import json
	import os
	import traceback

	import frappe
	from frappe.utils.password import get_decrypted_password

	from mypos.patches import v1_remove_sepay_api_key as PATCH

	DT, FN, CF = PATCH.DOCTYPE, PATCH.FIELDNAME, PATCH.CUSTOM_FIELD
	results, branch = [], None

	def ok(case, cond, extra=""):
		results.append((case, bool(cond)))
		print(f"{'PASS' if cond else 'FAIL'} {case} {extra}")

	def state():
		return {
			"custom_field": bool(frappe.db.exists("Custom Field", CF)),
			"column": bool(frappe.db.has_column(DT, FN)),
			"auth_rows": frappe.db.count("__Auth", {"doctype": DT, "fieldname": FN}),
		}

	clean = {"custom_field": False, "column": False, "auth_rows": 0}
	frappe.set_user("Administrator")
	try:
		print("== P1. Sau migrate ==")
		st = state()
		ok("P1a Không còn Custom Field / cột / giá trị key cũ", st == clean, f"({st})")
		fixture = os.path.join(frappe.get_app_path("mypos"), "fixtures", "custom_field.json")
		with open(fixture, encoding="utf-8") as f:
			names = {r.get("name") for r in json.load(f)}
		ok("P1b Fixture không còn field cũ, có sepay_webhook_secret", CF not in names and f"{DT}-sepay_webhook_secret" in names)

		print("== P2. Chạy lại patch (idempotent) ==")
		try:
			done = PATCH.execute()
			ok("P2 Không lỗi, không làm gì", done == {"auth_rows": 0, "custom_field": False, "column": False}, f"({done})")
		except Exception as e:  # noqa: BLE001
			ok("P2 Không lỗi, không làm gì", False, f"({type(e).__name__}: {e})")

		print("== P3. Giả lập site cũ ==")
		frappe.get_doc({"doctype": "Custom Field", "dt": DT, "fieldname": FN, "label": "ZZTEST key cũ", "fieldtype": "Password",
			"insert_after": "sepay_webhook_secret"}).insert(ignore_permissions=True)
		frappe.clear_cache(doctype=DT)
		branch = frappe.get_doc({"doctype": "Branch", "branch": "ZZTEST-PATCH-" + frappe.generate_hash(length=6)})
		branch.set(FN, "zz-old-key")
		branch.set("sepay_webhook_secret", "zz-hmac-secret")
		branch.insert(ignore_permissions=True)
		branch = branch.name
		frappe.db.commit()
		st = state()
		ok("P3a Đã dựng: có field + cột + giá trị key cũ", st["custom_field"] and st["column"] and st["auth_rows"] >= 1, f"({st})")
		done = PATCH.execute()
		frappe.db.commit()
		st = state()
		ok("P3b Patch xóa Custom Field, cột, giá trị key cũ", done["custom_field"] and done["column"] and done["auth_rows"] >= 1
			and st == clean, f"(done {done}, sau {st})")
		ok("P3c Branch còn, secret HMAC còn nguyên", frappe.db.exists(DT, branch)
			and get_decrypted_password(DT, branch, "sepay_webhook_secret", raise_exception=False) == "zz-hmac-secret")
		frappe.clear_cache(doctype=DT)
		ok("P3d Meta Branch không còn field cũ", not frappe.get_meta(DT).has_field(FN))
	except Exception:  # noqa: BLE001
		ok("Lỗi ngoài dự kiến", False)
		traceback.print_exc()
	finally:
		frappe.set_user("Administrator")
		try:
			frappe.db.rollback()
			if branch and frappe.db.exists(DT, branch):
				frappe.delete_doc(DT, branch, force=1, ignore_permissions=True)
			frappe.db.commit()
			if state() != clean:
				PATCH.execute()
				frappe.db.commit()
		except Exception:  # noqa: BLE001
			print(f"WARN dọn lỗi — xóa tay Branch {branch} và chạy lại mypos.patches.v1_remove_sepay_api_key.execute")
			traceback.print_exc()

	fails = [c for c, r in results if not r]
	print(f"KẾT QUẢ: {'PASS' if not fails else 'FAIL'} ({len(results) - len(fails)}/{len(results)})"
		+ (f" — lỗi: {', '.join(fails)}" if fails else ""))
	return {"ok": not fails, "results": results}
