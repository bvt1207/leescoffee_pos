import frappe
from frappe import _
from frappe.model.document import Document


class MYPOSOptionGroup(Document):
	"""Nhóm tùy chọn món (vd. Đường, Đá, Topping) do admin cấu hình trên Desk.

	Không có phụ thu ở giai đoạn này: extra_price của giá trị luôn bị bỏ qua.
	Quy tắc áp dụng cho món: xem option_resolver.py và .claude/rules/leescoffee_pos/options.md.
	"""

	def validate(self):
		self._validate_values()
		self._validate_targets()

	def on_update(self):
		_clear_cache()

	def on_trash(self):
		_clear_cache()

	def after_rename(self, *args, **kwargs):
		_clear_cache()

	def _validate_values(self):
		if not self.values:
			frappe.throw(_("Nhóm tùy chọn '{0}' cần ít nhất một giá trị.").format(self.title))

		seen = set()
		for row in self.values:
			label = (row.label or "").strip()
			if not label:
				frappe.throw(_("Dòng giá trị {0}: thiếu Nhãn.").format(row.idx))
			key = label.casefold()
			if key in seen:
				frappe.throw(_("Nhãn '{0}' bị trùng trong nhóm '{1}'.").format(label, self.title))
			seen.add(key)
			row.label = label
			if (row.extra_price or 0) < 0:
				frappe.throw(_("Phụ thu của '{0}' trong nhóm '{1}' không được âm.").format(label, self.title))

		defaults = [r for r in self.values if r.is_default and r.enabled]
		if self.selection_type == "Chọn 1" and len(defaults) > 1:
			frappe.throw(
				_("Nhóm '{0}' kiểu Chọn 1 chỉ được có một giá trị mặc định.").format(self.title)
			)
		if self.required and not defaults:
			frappe.msgprint(
				_(
					"Nhóm '{0}' bắt buộc chọn nhưng chưa có giá trị mặc định: "
					"đơn không gửi tùy chọn này sẽ bị từ chối."
				).format(self.title),
				indicator="orange",
				alert=True,
			)

	def _validate_targets(self):
		for row in self.targets or []:
			if row.target_type == "Item":
				if not row.item:
					frappe.throw(_("Dòng áp dụng {0}: chọn Mặt hàng.").format(row.idx))
				row.item_group = None
				row.include_children = 0
			else:
				if not row.item_group:
					frappe.throw(_("Dòng áp dụng {0}: chọn Nhóm hàng.").format(row.idx))
				row.item = None


def _clear_cache():
	from .option_resolver import clear_option_cache

	clear_option_cache()
