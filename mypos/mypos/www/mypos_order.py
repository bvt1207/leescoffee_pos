import frappe
from frappe.sessions import get_csrf_token

# Trang đặt món QR của khách: không cache (token phiên + trạng thái đơn đổi liên tục).
no_cache = 1


def get_context(context):
	"""Shell tối giản cho web đặt món QR (/order/<token>, route rule trong hooks.py).

	Không yêu cầu đăng nhập: khách là Guest, xác thực bằng mã QR + token phiên do
	api/customer_order_api.py cấp. Toàn bộ giao diện do React app (pos/src/order) dựng.
	Không đọc thương hiệu ở đây: frontend lấy từ get_shop (Branch) sau khi biết token QR.
	"""
	frappe.local.no_cache = True
	context.no_cache = 1
	context.title = "Đặt món"
	# Chỉ cần khi trình duyệt đang có phiên đăng nhập Desk (CSRF áp cho user không phải Guest).
	context.csrf_token = get_csrf_token() if frappe.session.user != "Guest" else ""
