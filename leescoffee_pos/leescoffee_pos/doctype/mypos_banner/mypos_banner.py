import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class MYPOSBanner(Document):
	"""Ảnh banner cho màn hình khách (/pos/customer). Không có dữ liệu mẫu: quản lý tạo trên Desk.

	pos_profile trống = hiển thị ở mọi POS Profile. Lọc + sắp xếp: api/customer_display_api.py.
	"""

	def validate(self):
		self.title = (self.title or "").strip()
		if self.valid_from and self.valid_upto and getdate(self.valid_from) > getdate(self.valid_upto):
			frappe.throw(_("\"Hiệu lực từ\" phải trước hoặc bằng \"Hiệu lực đến\"."))
		# Ảnh private vẫn xem được trên màn khách (đã đăng nhập) nhưng nên dùng ảnh public (CDN/cache trình duyệt).
		if (self.image or "").startswith("/private/"):
			frappe.msgprint(
				_("Ảnh banner đang là file private. Nên tải lại ảnh và bỏ chọn \"Is Private\"."),
				indicator="orange",
				alert=True,
			)
