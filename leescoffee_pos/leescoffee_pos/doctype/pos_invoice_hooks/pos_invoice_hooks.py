"""
Hooks for POS Invoice DocType to handle Leescoffee POS custom business logic:

- custom_kitchen_status chỉ được set khi đơn đã thanh toán.
- Quản lý buzzer gắn với đơn (chỉ cho order_type = Dine In).
- Buzzer reset chỉ khi:
  (a) huỷ đơn trước khi bắt đầu làm, hoặc
  (b) staff xác nhận khách lấy món.
"""

import frappe
from frappe import _


class PosInvoiceHooks:

	@staticmethod
	def on_submit(doc, method):
		"""
		Mỗi khi POS Invoice được submit.

		- Nếu đơn đã Paid và chưa có kitchen status,
		  khởi tạo trạng thái "Chưa làm".
		- Không auto-gán buzzer.
		"""
		if doc.status == "Paid" and not doc.custom_kitchen_status:
			doc.custom_kitchen_status = "Chưa làm"

			frappe.msgprint(
				_("Đơn đã thanh toán — bắt đầu vòng đời pha chế (Chưa làm).")
			)

	@staticmethod
	def before_save(doc, method):
		"""
		Trước khi lưu POS Invoice.

		Không chặn Draft POS Invoice có custom_kitchen_status
		vì POS có thể khởi tạo giá trị này trước khi submit.

		Business rule sẽ được xử lý khi invoice được submit.
		"""
		pass

	@staticmethod
	def on_update_after_submit(doc, method):
		"""
		Sau khi cập nhật POS Invoice đã submit.

		Không tự động reset buzzer.
		Buzzer chỉ reset qua:
		- on_cancel nếu đơn chưa bắt đầu làm
		- confirm_pickup khi khách đã lấy món
		"""
		pass

	@staticmethod
	def confirm_pickup(doc, method):
		"""
		Nhân viên xác nhận khách đã lấy món.

		Reset buzzer về "Sẵn sàng" nếu:
		- invoice có buzzer
		- kitchen status = "Đã hoàn thành"
		- buzzer hiện đang "Đang dùng"
		"""
		if doc.buzzer and doc.custom_kitchen_status == "Đã hoàn thành":
			buzzer = frappe.get_doc("Leescoffee Buzzer", doc.buzzer)

			if buzzer.status == "Đang dùng":
				buzzer.status = "Sẵn sàng"
				buzzer.save(ignore_permissions=True)

				frappe.msgprint(
					_("Buzzer {0} đã reset về Sẵn sàng (khách đã lấy món).").format(
						doc.buzzer
					)
				)

	@staticmethod
	def on_cancel(doc, method):
		"""
		Huỷ đơn → reset buzzer nếu đơn chưa bắt đầu làm.

		Nếu đơn đã bắt đầu/hoàn thành,
		buzzer không tự động reset tại đây.
		"""
		if doc.buzzer and doc.custom_kitchen_status in (None, "", "Chưa làm"):
			buzzer = frappe.get_doc("Leescoffee Buzzer", doc.buzzer)

			if buzzer.status == "Đang dùng":
				buzzer.status = "Sẵn sàng"
				buzzer.save(ignore_permissions=True)


# ============================================================
# Frappe Doc Events Wrappers
# ============================================================
#
# Frappe resolve handler theo dạng:
# module.attribute
#
# Vì vậy doc_events không trỏ trực tiếp vào:
# PosInvoiceHooks.on_submit
#
# mà trỏ vào các function cấp module bên dưới.
# Các function này delegate lại cho class PosInvoiceHooks.
#

def on_submit(doc, method):
	return PosInvoiceHooks.on_submit(doc, method)


def before_save(doc, method):
	return PosInvoiceHooks.before_save(doc, method)


def on_update_after_submit(doc, method):
	return PosInvoiceHooks.on_update_after_submit(doc, method)


def on_cancel(doc, method):
	return PosInvoiceHooks.on_cancel(doc, method)