"""Xóa field Branch.sepay_api_key (2026-11-28).

Webhook SePay xác thực bằng HMAC-SHA256 (Branch.sepay_webhook_secret, docs/rules/sepay.md §1); field cũ không còn tác dụng và
giá trị đã lưu được coi là đã lộ -> xóa hẳn, không sao lưu:
  1. Giá trị mã hóa trong bảng `__Auth` (doctype Branch, fieldname sepay_api_key).
  2. Custom Field "Branch-sepay_api_key" (đã bỏ khỏi fixture; fixture không tự xóa field ở site đã cài).
  3. Cột `sepay_api_key` của `tabBranch` (Custom Field.on_trash của Frappe không xóa cột).
Idempotent: field / cột / dữ liệu không còn thì bỏ qua. Chạy ở [post_model_sync]; fixture nạp sau patch nên không tạo lại field.
"""

import frappe

DOCTYPE = "Branch"
FIELDNAME = "sepay_api_key"
CUSTOM_FIELD = f"{DOCTYPE}-{FIELDNAME}"


def execute():
	done = {"auth_rows": 0, "custom_field": False, "column": False}

	done["auth_rows"] = frappe.db.count("__Auth", {"doctype": DOCTYPE, "fieldname": FIELDNAME})
	if done["auth_rows"]:
		frappe.db.delete("__Auth", {"doctype": DOCTYPE, "fieldname": FIELDNAME})

	if frappe.db.exists("Custom Field", CUSTOM_FIELD):
		frappe.delete_doc("Custom Field", CUSTOM_FIELD, force=True, ignore_permissions=True)
		done["custom_field"] = True

	if frappe.db.has_column(DOCTYPE, FIELDNAME):
		frappe.db.sql_ddl(f"ALTER TABLE `tab{DOCTYPE}` DROP COLUMN `{FIELDNAME}`")
		done["column"] = True

	frappe.clear_cache(doctype=DOCTYPE)
	print(
		f"mypos: xóa {CUSTOM_FIELD}: __Auth {done['auth_rows']} dòng, Custom Field {'đã xóa' if done['custom_field'] else 'không có'}, "
		f"cột {'đã xóa' if done['column'] else 'không có'}"
	)
	return done
