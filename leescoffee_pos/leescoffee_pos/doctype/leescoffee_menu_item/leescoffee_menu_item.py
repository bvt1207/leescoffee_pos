import frappe
from frappe import _
from frappe.utils import nowdate
from frappe.model.document import Document


class LeescoffeeMenuItem(Document):
	"""Child table của Leescoffee Menu: quản lý danh sách món.\n
	- Lấy thông tin từ Item, giá từ Item Price theo price_list của Menu.
	- Giá chỉ đọc; không sửa trực tiếp, thay đổi tại Item Price.
	- Template: không hiển thị giá. Variant: lấy giá của chính item_code Variant.
	"""

	def validate(self):
		"""Xử lý tự động khi thêm/sửa dòng: load Item, lấy giá từ Item Price."""
		self.load_item_details()

	def load_item_details(self):
		"""Load thông tin Item và lấy giá theo price_list của parent Menu."""
		if not self.item_code:
			return

		parent = self.parent_doc
		if not parent:
			return

		self.load_item_info()
		if parent.price_list:
			self.load_item_price(parent.price_list)

	@property
	def parent_doc(self):
		"""Get the parent Leescoffee Menu document."""
		if not self.parent:
			return None
		try:
			return frappe.get_doc("Leescoffee Menu", self.parent)
		except Exception:
			return None

	def load_item_info(self):
		"""Lấy Item Name, item_type (Stock/Service) từ Item."""
		if not frappe.db.exists("Item", self.item_code):
			frappe.throw(
				_("Item {0} không tồn tại. Vui lòng chọn Item có sẵn.").format(
					self.item_code
				)
			)

		item = frappe.get_doc("Item", self.item_code)

		# Lấy tên Item
		self.item_name = item.item_name or item.item_code

		# Loại hàng: dựa trên has_stock_field
		# Stock = có tồn kho (has_stock_field = 1), Service = dịch vụ
		self.item_type = "Stock" if item.has_stock_field else "Service"

	def load_item_price(self, price_list):
		"""Lấy giá từ Item Price theo item_code, price_list, selling = 1, VND.

		- Template (has_variants=1, variant_of=""): không lấy giá (không hiển thị).
		- Variant (variant_of!=""): lấy giá của chính item_code Variant, không lấy giá Template.
		- Enabled: lấy Item Price theo chính item_code này.
		- Chỉ lấy price_list có selling = 1.
		- Chỉ lấy Item Price đang có hiệu lực (valid_from/valid_upto). Chấp nhận valid_from hoặc valid_upto bị trống (None).
		"""
		# Lấy thông tin Item để xác định Template/Variant
		item_doc = frappe.db.get_value(
			"Item", self.item_code,
			["has_variants", "variant_of", "disabled"],
			as_dict=1,
		)

		# Item bị disable không được thêm vào menu
		if item_doc.disabled:
			frappe.throw(
				_("Item {0} đã bị vô hiệu hóa. Vui lòng chọn Item khác.").format(
					self.item_code
				)
			)

		# Template: có biến thể nhưng không phải là variant của item nào
		is_template = item_doc.has_variants and not item_doc.variant_of
		if is_template:
			# Template không có giá
			self.price = None
			return

		# Variant hoặc Enabled: lấy Item Price theo chính item_code này
		today = nowdate()
		item_prices = frappe.db.get_list(
			"Item Price",
			filters={
				"item_code": self.item_code,
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
				self.price = ip.price_list_rate or 0.0
				return

		self.price = None
