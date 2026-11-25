"""Sửa POS Invoice.payment_status lệch (2026-11-25). Idempotent.

Trước đây chỉ webhook SePay ghi "Đã thanh toán"; thu tiền mặt / submit tay giữ default "Chưa thanh toán", hủy không ghi "Hủy".
Từ 2026-11-25 hook before_submit / on_cancel (pos_invoice_hooks.py) + order_cancel.cancel_draft tính field này.

- docstatus 1, không phải trả hàng (Paid / Consolidated), khác "Đã thanh toán" -> "Đã thanh toán"
- docstatus 2, không phải trả hàng, khác "Hủy" -> "Hủy" (cờ custom_late_payment giữ nguyên)
- Đơn trả hàng (is_return = 1) và đơn nháp: KHÔNG đụng.

UPDATE SQL trực tiếp: không đổi `modified`, không chạy hook, không tạo Version, không gửi realtime / thông báo.
"""

import frappe

PAID = "Đã thanh toán"
CANCELLED = "Hủy"
RULES = ((1, PAID), (2, CANCELLED))


def execute():
	if not frappe.db.has_column("POS Invoice", "payment_status"):
		print("[payment_status] Chưa có cột payment_status: bỏ qua")
		return
	for docstatus, value in RULES:
		cond = "`docstatus` = %(ds)s AND IFNULL(`is_return`, 0) = 0 AND IFNULL(`payment_status`, '') != %(v)s"
		params = {"ds": docstatus, "v": value}
		rows = frappe.db.sql(
			f"SELECT `status`, COUNT(*) AS n FROM `tabPOS Invoice` WHERE {cond} GROUP BY `status`", params, as_dict=True
		)
		total = sum(r.n for r in rows)
		if not total:
			print(f"[payment_status] docstatus {docstatus}: không có đơn lệch")
			continue
		sample = frappe.db.sql(
			f"SELECT `name` FROM `tabPOS Invoice` WHERE {cond} ORDER BY `creation` DESC LIMIT 20", params, pluck=True
		)
		frappe.db.sql(f"UPDATE `tabPOS Invoice` SET `payment_status` = %(v)s WHERE {cond}", params)
		by_status = ", ".join(f"{r.status}: {r.n}" for r in rows)
		print(f"[payment_status] docstatus {docstatus} -> {value}: {total} đơn ({by_status}); vd. {', '.join(sample)}")
	frappe.db.commit()
