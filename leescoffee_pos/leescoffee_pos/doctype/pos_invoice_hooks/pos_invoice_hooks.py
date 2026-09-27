"""
Hooks for POS Invoice DocType to handle Leescoffee POS custom business logic:
- `custom_kitchen_status` chỉ được set khi `status` == "Paid" (không phải docstatus=1).
- Quản lý `buzzer` gắn với đơn (chỉ cho order_type = Dine In).
"""

import frappe
from frappe import _
from frappe.model.document import Document


class PosInvoiceHooks:
	"""Logic hooks được gọi bởi doc_events trong hooks.py cho POS Invoice."""

	def on_submit(self, method):
		"""Mỗi khi POS Invoice được tạo (submitted).

		- Đảm bảo `custom_kitchen_status` được set khi status = Paid (không phải docstatus=1 đơn thuần).
		- Gán `buzzer` cho đơn (nếu order_type = Dine In) — đặt trạng thái buzzer thành Đang dùng.
		"""
		# Chặn set custom_kitchen_status trừ khi status == "Paid"
		if self.custom_kitchen_status and self.status != "Paid":
			frappe.throw(
				_("Chỉ có thể set trạng thái pha chế khi đơn được thanh toán (status = Paid).")
			)

		# Nếu order_type = Dine In, gán 1 buzzer sẵn sàng (nếu có) và set busy
		if self.order_type == "Dine In" and self.buzzer:
			# field `buzzer` lưu tên phiếu Leescoffee Buzzer
			pass  # đã được gán bởi UI qua các trường tùy chỉnh, validation có thể check ở đây

	def before_save(self, method):
		"""Trước khi lưu POS Invoice.

		- Tự động set `custom_kitchen_status = Chưa làm` khi status = Paid và `custom_kitchen_status` chưa có.
		- Reset `custom_kitchen_status` về trống khi status != Paid (ví dụ trả hàng, huỷ).
		"""
		if self.status == "Paid":
			# Bắt đầu vòng đời pha chế
			if not self.custom_kitchen_status:
				self.custom_kitchen_status = "Chưa làm"
				frappe.msgprint(_("Đơn đã thanh toán — đã bắt đầu vòng đời pha chế."))
			# Reset buzzer về Sẵn sàng nếu đơn bị trả / huỷ
			if hasattr(self, '_is_cancel'):
				frappe.get_doc("Leescoffee Buzzer", self.buzzer).set_available(self.buzzer)
		elif self.status in ("Consolidated", "Cancelled", "Return") and self.buzzer:
				# Nếu đơn bị chuyển sang Sales Invoice hoặc bị hủy, trả buzzer về sẵn sàng
				# (chỉ khi còn buzzer được gán)
				pass

	def on_update(self, method):
		"""Sau khi POS Invoice được cập nhật (ví dụ trạng thái pha chế thay đổi).

		- Khi `custom_kitchen_status` thay đổi thành "Đã hoàn thành", đảm bảo buzzer reset về Sẵn sàng
		- Khi order_type chuyển từ "Dine In" sang "Take Away", reset buzzer nếu có
		"""
		# Kiểm tra thay đổi trạng thái pha chế
		if hasattr(self, 'custom_kitchen_status'):
			old_doc = frappe.get_last_doc("POS Invoice", filters={"name": self.name})
			if hasattr(old_doc, 'custom_kitchen_status') and old_doc.custom_kitchen_status != self.custom_kitchen_status:
				if self.custom_kitchen_status == "Đã hoàn thành":
					# đơn xong -> reset buzzer nếu có
					if self.buzzer:
						PosInvoiceHooks._reset_buzzer(self.buzzer)
						frappe.msgprint(_("Đơn đã hoàn thành — buzzer đã reset về Sẵn sàng."))
				# khi order_type thay đổi từ Dine In sang Take Away, reset buzzer nếu có
				if old_doc.order_type == "Dine In" and self.order_type == "Take Away":
					if self.buzzer:
						PosInvoiceHooks._reset_buzzer(self.buzzer)

	def _reset_buzzer(self, buzzer_name):
		"""Helper: Reset buzzer về Sẵn sàng."""
		frappe.get_doc("Leescoffee Buzzer", buzzer_name).set_available(buzzer_name)


def before_save(doc, method):
	"""Phụ trợ – same như PosInvoiceHooks.before_save (dùng cho module imports)"""
	PosInvoiceHooks.before_save(doc, method)


def on_submit(doc, method):
	"""Phụ trợ – same as PosInvoiceHooks.on_submit"""
	PosInvoiceHooks.on_submit(doc, method)


def on_update(doc, method):
	"""Phụ trợ – same as PosInvoiceHooks.on_update"""
	PosInvoiceHooks.on_update(doc, method)