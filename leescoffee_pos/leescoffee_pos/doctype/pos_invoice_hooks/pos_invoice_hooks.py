"""
Hooks for POS Invoice DocType to handle Leescoffee POS custom business logic:
- `custom_kitchen_status` chỉ được set khi `status` == "Paid".
- Quản lý `buzzer` gắn với đơn (chỉ cho order_type = Dine In).
- Buzzer reset chỉ khi: (a) huỷ đơn trước khi bắt đầu làm, hoặc (b) staff xác nhận khách lấy món.
"""

import frappe
from frappe import _


@staticmethod
def on_submit(doc, method):
	"""Mỗi khi POS Invoice được submit (on_submit).

	- Đảm bảo `custom_kitchen_status` được set khi status == "Paid".
	- Không auto-gán buzzer; UI sẽ gán nếu order_type = Dine In.
	"""
	if doc.status == "Paid" and not doc.custom_kitchen_status:
		doc.custom_kitchen_status = "Chưa làm"
		frappe.msgprint(_("Đơn đã thanh toán — bắt đầu vòng đời pha chế (Chưa làm)."))


@staticmethod
def before_save(doc, method):
	"""Trước khi lưu POS Invoice (before_save).

	- Chặn set custom_kitchen_status nếu status != "Paid".
	"""
	if doc.custom_kitchen_status and doc.status != "Paid":
		frappe.throw(
			_("Chỉ có thể set trạng thái pha chế khi đơn được thanh toán (status = Paid).")
		)


@staticmethod
def on_update_after_submit(doc, method):
	"""Sau khi cập nhật POS Invoice đã submit.

	- Không làm gì tự động. Buzzer reset không auto xảy ra ở đây.
	  Reset buzzer chỉ qua: (a) on_cancel nếu chưa bắt đầu làm, (b) confirm_pickup.
	"""
	pass


@staticmethod
def confirm_pickup(doc, method):
	"""Nhân viên xác nhận khách đã lấy món → reset buzzer về Sẵn sàng.

	Gọi qua button trên UI Status board.
	Chỉ reset nếu buzzer đang Đang dùng và đơn đã Đã hoàn thành.
	"""
	if doc.buzzer and doc.custom_kitchen_status == "Đã hoàn thành":
		buzzer = frappe.get_doc("Leescoffee Buzzer", doc.buzzer)
		if buzzer.status == "Đang dùng":
			buzzer.status = "Sẵn sàng"
			buzzer.save(ignore_permissions=True)
			frappe.msgprint(
				_("Buzzer {0} đã reset về Sẵn sàng (khách đã lấy món).").format(doc.buzzer)
			)


@staticmethod
def on_cancel(doc, method):
	"""Huỷ đơn → reset buzzer ngay nếu đơn chưa bắt đầu làm (Chưa làm).

	Nếu đơn đã Đã làm, buzzer giữ Đang dùng cho đến khi staff xác nhận pickup.
	"""
	if doc.buzzer and doc.custom_kitchen_status in (None, "", "Chưa làm"):
		buzzer = frappe.get_doc("Leescoffee Buzzer", doc.buzzer)
		if buzzer.status == "Đang dùng":
			buzzer.status = "Sẵn sàng"
			buzzer.save(ignore_permissions=True)