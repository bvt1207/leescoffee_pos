"""Bỏ default "100" của Custom Field POS Invoice Item.sugar_level / ice_level (2026-11-20).

Lý do: default làm mọi dòng mới bị điền 100/100, kể cả món không có Option Group; trước khi sửa
`read_line_options`, đơn như vậy hiện "Đường 100% · Đá 100%". Cột cũ giờ chỉ được ghi khi:
request kiểu cũ (không có khóa `options`), request gửi rõ sugar/ice, hoặc Option Group có `legacy_field`.

Idempotent, chỉ đổi định nghĩa field: không sửa dữ liệu đơn đã có (kể cả đơn Paid/Consolidated).
Lưu bằng doc.save() để Frappe cập nhật luôn DEFAULT của cột trong DB. Fixture `custom_field.json`
cũng đã để default null (fixture nạp sau patch, cùng giá trị).
"""

import frappe

FIELDS = ("POS Invoice Item-sugar_level", "POS Invoice Item-ice_level")


def execute():
	changed = []
	for name in FIELDS:
		if not frappe.db.exists("Custom Field", name):
			print(f"[legacy_option_default] Không có Custom Field {name}: bỏ qua")
			continue
		doc = frappe.get_doc("Custom Field", name)
		if not doc.default:
			continue
		doc.default = None
		doc.save(ignore_permissions=True)
		changed.append(name)

	if changed:
		frappe.clear_cache(doctype="POS Invoice Item")
	print(f"[legacy_option_default] Đã bỏ default: {changed or 'không có gì cần đổi'}")
