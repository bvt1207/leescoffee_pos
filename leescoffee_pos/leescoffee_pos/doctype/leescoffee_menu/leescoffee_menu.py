import frappe
from frappe import _
from frappe.utils import nowdate
from frappe.model.document import Document


class LeescoffeeMenu(Document):
	"""Main DocType quản lý Menu món ăn/đu ěi cho POS.\n
	- Chọn Price List có sẵn ERPNext.
	- Child table Leescoffee Menu Item chứa danh sách món.
	- Giá được tự động load từ Item Price theo price_list selected.
	"""

	def validate(self):
		"""Validate menu: đảm bảo ít nhất 1 món có sẵn."""
		if not self.items:
			frappe.throw(
				_("Menu {0} phải có ít nhất 1 món.").format(self.menu_name or self.name)
			)

	@staticmethod
	def get_menu_with_items(price_list=None):
		"""Lấy menu kèm món đã cấu hình.\n
		Args:\n			price_list: Name of Price List. Nếu None dùng default.\n
		Returns:\n			dict{'menu_name': ..., 'price_list': ..., 'items': [...]}"""
		filters = {}
		if price_list:
			filters["price_list"] = price_list

		menus = frappe.get_all(
			"Leescoffee Menu",
			filters=filters,
			fields=["name", "menu_name", "price_list"],
		)

		result = []
		for menu in menus:
			items = frappe.get_all(
				"Leescoffee Menu Item",
				filters={"parent": menu.name},
				fields=[
					"stt",
					"item_code",
					"item_name",
					"item_type",
					
					"price",
				],
			)

			result.append(
				{
					"name": menu.name,
					"menu_name": menu.menu_name,
					"price_list": menu.price_list,
					"items": items,
				}
			)

		return result

	@staticmethod
	def get_price_for_item(item_code, price_list):
		"""Lấy giá bán của 1 item theo 1 price_list (dùng cho frontend hoặc báo cáo).

		- Nếu item bị Disable → báo lỗi.
		- Nếu item là Template → trả None.
		- Nếu tìm thấy Item Price đang có hiệu lực → trả giá.
		- Ngược lại (hết hạn hoặc không có) → trả 0.0.
		"""
		if not frappe.db.exists("Item", item_code):
			frappe.throw(_("Item {0} không tồn tại.").format(item_code))

		# Kiểm tra Item bị disabled
		item_doc = frappe.db.get_value(
			"Item", item_code,
			["disabled", "has_variants", "variant_of"],
			as_dict=1,
		)
		if item_doc.disabled:
			frappe.throw(
				_("Item {0} đã bị vô hiệu hóa. Vui lòng chọn Item khác.").format(
					item_code
				)
			)

		# Lấy thông tin Template/Variant
		is_template = item_doc.has_variants and not item_doc.variant_of

		# Template: không có giá
		if is_template:
			return None

		# Lấy Item Price đang có hiệu lực (kiểm tra valid_from/valid_upto)
		# Chấp nhận valid_from hoặc valid_upto bị trống (None)
		today = nowdate()
		item_prices = frappe.db.get_list(
			"Item Price",
			filters={
				"item_code": item_code,
				"price_list": price_list,
				"selling": 1,
				"currency": "VND",
			},
			fields=["price_list_rate", "valid_from", "valid_upto"],
			order_by="valid_from desc",
		)

		for ip in item_prices:
			valid_from_ok = ip.valid_from is None or ip.valid_from <= today
			valid_upto_ok = ip.valid_upto is None or ip.valid_upto >= today
			if valid_from_ok and valid_upto_ok:
				return float(ip.price_list_rate) if ip.price_list_rate else 0.0

		return 0.0