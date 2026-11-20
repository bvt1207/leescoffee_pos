from frappe.model.document import Document


class MYPOSOrderCancelLog(Document):
	"""Nhật ký hủy đơn Draft — đơn POS Invoice bị xóa nên log nằm ở DocType riêng (Comment bị xóa theo đơn).

	Chỉ tạo qua `order_cancel.cancel_draft_with_log` (ignore_permissions). Quản lý chỉ sửa `needs_review`.
	Quy tắc: .claude/rules/leescoffee_pos/order-qr.md (hết hạn QR) và roles.md (đóng ca, hủy đơn).
	"""
