"""Đơn giản hóa hủy đơn / xử lý đơn dở (2026-11-23).

Bỏ: DocType "MYPOS Order Cancel Log", Script Report "MYPOS Review Queue", Custom Field POS Invoice.needs_review,
trạng thái pha chế "Đã đóng ca chưa xử lý" (đóng ca bắt buộc). Hủy đơn nay = POS Invoice chuyển Cancelled + custom_cancel_reason.

DocType / Report là file chuẩn của app: xóa thư mục trong repo thì bản ghi trong DB VẪN CÒN -> patch này xóa.
Custom Field: fixture custom_field.json đã bỏ needs_review (fixture nạp SAU patch, không tạo lại).

[post_model_sync]. Idempotent: chạy lại khi đã dọn thì không làm gì (bước 1 chỉ chạy khi Custom Field needs_review còn,
hoặc còn đơn mang trạng thái cũ).
Thứ tự: (1) dọn dữ liệu đơn -> (2) sao lưu log hủy ra File private -> (3) xóa Report -> (4) xóa Custom Field
-> (5) xóa DocType + bảng -> (6) gỡ Workspace Link.
"""

import json

import frappe
from frappe.utils import now_datetime

LOG_DOCTYPE = "MYPOS Order Cancel Log"
REPORT = "MYPOS Review Queue"
NEEDS_REVIEW_FIELD = "POS Invoice-needs_review"
LEGACY_SHIFT_CLOSED = "Đã đóng ca chưa xử lý"
LEGACY_TARGET = "Không thực hiện được"  # Van chốt mặc định (plan D1)
WORKSPACE = "leescoffee_pos"


def _append_reason(name, old, text):
	return (old + " | " if old else "") + text


def _cleanup_orders():
	"""(1) Đơn "Đã đóng ca chưa xử lý" -> LEGACY_TARGET; đơn needs_review = 1 giữ trạng thái. Ghi lý do + Comment."""
	has_flag = frappe.db.exists("Custom Field", NEEDS_REVIEW_FIELD) and frappe.db.has_column("POS Invoice", "needs_review")
	cond = "`custom_kitchen_status` = %(legacy)s"
	if has_flag:
		cond += " OR IFNULL(`needs_review`, 0) = 1"
	rows = frappe.db.sql(
		f"SELECT `name`, `custom_kitchen_status`, `kitchen_outcome_reason` FROM `tabPOS Invoice` WHERE {cond}",
		{"legacy": LEGACY_SHIFT_CLOSED},
		as_dict=True,
	)
	moved = flagged = 0
	for r in rows:
		values = {}
		if r.custom_kitchen_status == LEGACY_SHIFT_CLOSED:
			values["custom_kitchen_status"] = LEGACY_TARGET
			note = f"Dọn dữ liệu cũ: '{LEGACY_SHIFT_CLOSED}' -> '{LEGACY_TARGET}' (bỏ đóng ca bắt buộc)"
			moved += 1
		else:
			note = "Dọn dữ liệu cũ: bỏ cờ 'Cần xem lại'"
			flagged += 1
		values["kitchen_outcome_reason"] = _append_reason(r.name, r.kitchen_outcome_reason or "", note)
		if has_flag:
			values["needs_review"] = 0
		frappe.db.set_value("POS Invoice", r.name, values, update_modified=False)
		frappe.get_doc(
			{
				"doctype": "Comment",
				"comment_type": "Info",
				"reference_doctype": "POS Invoice",
				"reference_name": r.name,
				"content": note + ".",
			}
		).insert(ignore_permissions=True)
	frappe.db.commit()
	print(f"[simplify_cancel_review] Dọn dữ liệu: {moved} đơn '{LEGACY_SHIFT_CLOSED}' -> '{LEGACY_TARGET}', {flagged} đơn bỏ cờ")


def _backup_cancel_log():
	"""(2) Sao lưu toàn bộ log hủy ra File private (đơn gốc đã bị xóa nên không gắn ngược vào đơn được)."""
	if not frappe.db.table_exists(LOG_DOCTYPE):
		return
	rows = frappe.db.sql(f"SELECT * FROM `tab{LOG_DOCTYPE}` ORDER BY `creation`", as_dict=True)
	if not rows:
		print("[simplify_cancel_review] Cancel Log rỗng: không sao lưu")
		return
	file_name = f"mypos_order_cancel_log_backup_{now_datetime().strftime('%Y%m%d_%H%M%S')}.json"
	frappe.get_doc(
		{
			"doctype": "File",
			"file_name": file_name,
			"is_private": 1,
			"content": json.dumps(rows, ensure_ascii=False, default=str, indent=1),
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()
	print(f"[simplify_cancel_review] Sao lưu {len(rows)} dòng Cancel Log -> File private {file_name}")
	pending = [
		r for r in rows if r.get("needs_review") or (r.get("orphan_transaction_ref") or "").strip()
	]
	for r in pending:
		print(
			"   CẦN ĐỐI SOÁT: log={0} đơn={1} giao_dịch={2} số_tiền={3}".format(
				r.get("name"), r.get("invoice_name"), r.get("orphan_transaction_ref"), r.get("orphan_amount")
			)
		)


def _delete_report():
	"""(3) Report chuẩn của app: Report.on_trash cho xóa khi in_patch."""
	if frappe.db.exists("Report", REPORT):
		frappe.delete_doc("Report", REPORT, force=1, ignore_missing=True, ignore_permissions=True)
		print(f"[simplify_cancel_review] Đã xóa Report {REPORT}")


def _delete_custom_field():
	"""(4) Custom Field needs_review (on_trash xóa Property Setter của field). Cột DB có thể còn — vô hại."""
	if frappe.db.exists("Custom Field", NEEDS_REVIEW_FIELD):
		frappe.delete_doc("Custom Field", NEEDS_REVIEW_FIELD, force=1, ignore_missing=True, ignore_permissions=True)
		frappe.clear_cache(doctype="POS Invoice")
		print(f"[simplify_cancel_review] Đã xóa Custom Field {NEEDS_REVIEW_FIELD}")


def _delete_doctype():
	"""(5) DocType chuẩn của app (mẫu v1_remove_pos_settings): quyền, link, thông báo, DocType, bảng."""
	for dt, field in (
		("Custom DocPerm", "parent"),
		("Property Setter", "doc_type"),
		("Custom Field", "dt"),
		("Notification Log", "document_type"),
	):
		if frappe.db.table_exists(dt) and frappe.db.has_column(dt, field):
			frappe.db.delete(dt, {field: LOG_DOCTYPE})
	if frappe.db.exists("DocType", LOG_DOCTYPE):
		frappe.delete_doc("DocType", LOG_DOCTYPE, force=1, ignore_missing=True, ignore_permissions=True)
		print(f"[simplify_cancel_review] Đã xóa DocType {LOG_DOCTYPE}")
	frappe.db.commit()
	if frappe.db.table_exists(LOG_DOCTYPE):
		frappe.db.sql_ddl(f"DROP TABLE IF EXISTS `tab{LOG_DOCTYPE}`")
		print(f"[simplify_cancel_review] Đã xóa bảng tab{LOG_DOCTYPE}")


def _remove_links():
	"""(6) Link còn sót trên Workspace / Sidebar / Desktop Icon (bảng có thể không có ở bản khác)."""
	for child, field in (
		("Workspace Link", "link_to"),
		("Workspace Shortcut", "link_to"),
		("Workspace Sidebar Item", "link_to"),
		("Desktop Icon", "link_to"),
	):
		if frappe.db.table_exists(child) and frappe.db.has_column(child, field):
			for target in (LOG_DOCTYPE, REPORT):
				frappe.db.delete(child, {field: target})
	frappe.db.commit()


def execute():
	_cleanup_orders()
	_backup_cancel_log()
	_delete_report()
	_delete_custom_field()
	_delete_doctype()
	_remove_links()
	frappe.clear_cache()
