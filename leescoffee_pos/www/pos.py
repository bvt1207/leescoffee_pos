import frappe
from frappe import _
from frappe.sessions import get_csrf_token

# Trang POS chứa CSRF token theo session -> không được cache lại.
no_cache = 1


def get_context(context):
	"""Context cho trang POS (www/pos.html).

	Trang này là shell tối giản: toàn bộ giao diện do React app
	(leescoffee_pos/pos) dựng, script được nạp từ /assets/leescoffee_pos/pos/.
	"""
	if frappe.session.user == "Guest":
		frappe.throw(
			_("Bạn cần đăng nhập để sử dụng màn hình POS."),
			frappe.PermissionError,
		)

	# Không cache trang (token theo session + dữ liệu đơn thay đổi liên tục)
	frappe.local.no_cache = True
	context.no_cache = 1

	# Tiêu đề trang: tên thương hiệu lấy từ API, ở đây chỉ dùng nhãn chung.
	context.title = "POS"
	context.csrf_token = get_csrf_token()
