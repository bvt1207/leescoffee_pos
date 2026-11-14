import secrets

import frappe
from frappe import _
from frappe.model.document import Document

# Đường dẫn công khai của web đặt món (frontend giai đoạn 2 phục vụ route này).
ORDER_ROUTE = "/order/"
TOKEN_BYTES = 18  # token_urlsafe(18) -> 24 ký tự, ~144 bit ngẫu nhiên


def build_order_url(token):
	return frappe.utils.get_url(ORDER_ROUTE + token)


class MYPOSOrderQR(Document):
	"""Mã QR đặt món dán tại quán. Mỗi chi nhánh có thể có nhiều mã; thu hồi bằng `enabled = 0`.

	Quy tắc + mô hình bảo mật: .claude/rules/leescoffee_pos/order-qr.md.
	"""

	def before_insert(self):
		self.token = secrets.token_urlsafe(TOKEN_BYTES)

	def validate(self):
		if not self.token:
			self.token = secrets.token_urlsafe(TOKEN_BYTES)
		elif not self.is_new() and self.has_value_changed("token"):
			frappe.throw(_("Không được sửa mã bí mật. Hãy tắt mã này và tạo mã mới."))
		self.order_url = build_order_url(self.token)

		if self.enabled and not frappe.db.exists(
			"POS Profile", {"branch": self.branch, "disabled": 0}
		):
			frappe.msgprint(
				_("Chi nhánh {0} chưa có POS Profile đang bật: khách quét mã sẽ chưa đặt món được.").format(
					self.branch
				),
				indicator="orange",
			)


def qr_svg(text, scale=6):
	"""SVG (chuỗi) của mã QR. Dùng thư viện pyqrcode đi kèm Frappe (dùng cho 2FA).

	Trả None nếu thư viện không có (không thêm phụ thuộc mới).
	"""
	from io import BytesIO

	try:
		import pyqrcode
	except ImportError:
		return None

	stream = BytesIO()
	pyqrcode.create(text, error="M").svg(stream, scale=scale, xmldecl=False, svgclass="mypos-qr", omithw=True)
	return stream.getvalue().decode("utf-8")


@frappe.whitelist()
def get_qr_image(name):
	"""URL + SVG mã QR để in (chỉ user có quyền đọc mã)."""
	doc = frappe.get_doc("MYPOS Order QR", name)
	doc.check_permission("read")
	url = build_order_url(doc.token)
	return {
		"name": doc.name,
		"branch": doc.branch,
		"enabled": doc.enabled,
		"url": url,
		"svg": qr_svg(url),
	}
