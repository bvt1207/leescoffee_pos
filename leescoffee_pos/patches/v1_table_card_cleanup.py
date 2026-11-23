"""Thẻ bàn (2026-11-23, đổi từ thẻ rung; DocType vẫn MYPOS Buzzer): trả thẻ kẹt "Đang dùng" về "Sẵn sàng".

Kẹt = status "Đang dùng" nhưng không còn đơn Dine In docstatus 0/1 nào giữ (pha chế chưa kết thúc) — dữ liệu cũ
(đơn hủy kiểu cũ, sửa tay). Từ 2026-11-23 "đang dùng" tính theo đơn (pos_api._held_buzzers) nên thẻ kẹt không còn
bị khóa; patch chỉ cho field status trên Desk khớp thực tế. Idempotent, in danh sách thẻ đã sửa. Không đụng đơn.
"""

import frappe


def execute():
	from leescoffee_pos.leescoffee_pos.doctype.pos_invoice_hooks.kitchen_status import KITCHEN_TERMINAL_STATUSES

	if not frappe.db.table_exists("MYPOS Buzzer"):
		print("[table_card_cleanup] Không có bảng MYPOS Buzzer: bỏ qua")
		return
	busy = frappe.get_all("MYPOS Buzzer", filters={"status": "Đang dùng"}, fields=["name", "buzzer_number", "branch"])
	fixed = []
	for b in busy:
		holders = [
			r.name
			for r in frappe.get_all(
				"POS Invoice",
				filters={"order_type": "Dine In", "docstatus": ["in", [0, 1]], "buzzer": b.name},
				fields=["name", "custom_kitchen_status"],
			)
			if (r.custom_kitchen_status or "") not in KITCHEN_TERMINAL_STATUSES
		]
		if holders:
			continue
		frappe.db.set_value("MYPOS Buzzer", b.name, "status", "Sẵn sàng", update_modified=False)
		fixed.append(f"{b.buzzer_number} ({b.branch})")
	frappe.db.commit()
	print(f"[table_card_cleanup] Thẻ 'Đang dùng': {len(busy)}; trả về 'Sẵn sàng': {len(fixed)} {fixed}")
