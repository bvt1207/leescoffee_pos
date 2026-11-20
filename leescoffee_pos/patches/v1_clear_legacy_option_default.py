"""Cột cũ POS Invoice Item.sugar_level / ice_level không tự có giá trị (2026-11-20).

1. Bỏ default "100".
2. Options thêm dòng trống ở đầu ("\n50\n70\n100"): Frappe gán lựa chọn ĐẦU TIÊN cho Select không có default
   (frappe/model/create_new.py::get_static_default_value) -> không có dòng trống thì dòng mới nhận "50".
   Chạy lại bằng nhãn "#2026-11-20 blank-first-option" trong patches.txt.

Lý do: default làm mọi dòng mới bị điền 100/100, kể cả món không có Option Group; trước khi sửa
`read_line_options`, đơn như vậy hiện "Đường 100% · Đá 100%". Cột cũ giờ chỉ được ghi khi:
request kiểu cũ (không có khóa `options`), request gửi rõ sugar/ice, hoặc Option Group có `legacy_field`.

Idempotent, chỉ đổi định nghĩa field: không sửa dữ liệu đơn đã có (kể cả đơn Paid/Consolidated).
Lưu bằng doc.save() để Frappe cập nhật luôn DEFAULT của cột trong DB. Fixture `custom_field.json`
cũng đã để default null (fixture nạp sau patch, cùng giá trị).
"""

import frappe

FIELDS = ("POS Invoice Item-sugar_level", "POS Invoice Item-ice_level")
DEFAULT_OPTIONS = "50\n70\n100"


def execute():
	changed = []
	for name in FIELDS:
		if not frappe.db.exists("Custom Field", name):
			print(f"[legacy_option_default] Không có Custom Field {name}: bỏ qua")
			continue
		doc = frappe.get_doc("Custom Field", name)
		blank_first = (doc.options or "").startswith("\n")
		if not doc.default and blank_first:
			continue
		doc.default = None
		if not blank_first:
			doc.options = "\n" + ((doc.options or "").strip() or DEFAULT_OPTIONS)
		doc.save(ignore_permissions=True)
		changed.append(name)

	if changed:
		frappe.clear_cache(doctype="POS Invoice Item")
	print(f"[legacy_option_default] Đã bỏ default + thêm lựa chọn trống đầu: {changed or 'không có gì cần đổi'}")
