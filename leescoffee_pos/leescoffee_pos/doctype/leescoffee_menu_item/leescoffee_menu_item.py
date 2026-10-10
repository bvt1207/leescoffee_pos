import frappe
from frappe import _
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
		"""Lấy Item Name, item_type (Stock/Service), item_status từ Item."""
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

		# Trạng thái Item
		self.item_status = item.status

	def load_item_price(self, price_list):
		"""Lấy giá từ Item Price theo item_code, price_list, selling = 1, VND.

		- Template: không lấy giá (không hiển thị).
		- Variant: lấy giá của chính item_code Variant, không lấy giá Template.
		- Chỉ lấy price_list có selling = 1.
		- Giá đã hiệu lực theo valid_from / valid_till.
		"""
		if self.item_status == "Template":
			# Template không có giá
			self.price = None
			return

		# Variant / Enabled: lấy Item Price theo chính item_code này
		item_price = frappe.db.get_value(
			"Item Price",
			filters={
				"item_code": self.item_code,
				"price_list": price_list,
				"selling": 1,
				"currency": "VND",
			},
			fieldname=["price_list_rate"],
		)

		self.price = item_price or 0.0
