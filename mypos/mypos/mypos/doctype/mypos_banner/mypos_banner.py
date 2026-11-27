import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate


class MYPOSBanner(Document):
	"""Ảnh banner cho màn hình khách (/pos/customer). Không có dữ liệu mẫu: quản lý tạo trên Desk.

	pos_profile trống = hiển thị ở mọi POS Profile. Lọc + sắp xếp: `active_banners` (dùng chung /pos/customer và /order).
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


def active_banners(pos_profile, public_only=False, limit=None):
	"""Banner đang hiệu lực của POS Profile: enabled, pos_profile trống hoặc = profile, trong khoảng hiệu lực, có ảnh.
	Sắp sort_order rồi creation. Nguồn DUY NHẤT cho màn khách (/pos/customer) và trang đăng nhập /order.

	public_only=True: bỏ ảnh /private/ (khách /order là Guest, không xem được file private).
	"""
	today = getdate(nowdate())
	rows = frappe.get_all(
		"MYPOS Banner",
		filters={"enabled": 1},
		or_filters=[["pos_profile", "is", "not set"], ["pos_profile", "=", pos_profile]],
		fields=["title", "image", "valid_from", "valid_upto"],
		order_by="sort_order asc, creation asc",
	)
	out = []
	for r in rows:
		if not r.image or (public_only and r.image.startswith("/private/")):
			continue
		if (r.valid_from and getdate(r.valid_from) > today) or (r.valid_upto and getdate(r.valid_upto) < today):
			continue
		out.append({"title": r.title, "image": r.image})
		if limit and len(out) >= limit:
			break
	return out
