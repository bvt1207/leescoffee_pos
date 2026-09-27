import frappe
from frappe import _
from frappe.model.document import Document


class LeescoffeeBuzzer(Document):
	"""Thẻ rung vật lý cho khách Dine In tại quầy.

	Mỗi thẻ có một số duy nhất trong 1 chi nhánh (branch).
	Trạng thái: Sẵn sàng / Đang dùng (khi đã được gán cho đơn POS Invoice hiện tại).
	"""

	def validate(self):
		"""Kiểm tra tính duy nhất của (buzzer_number, branch) trong DB."""
		self._validate_unique_buzzer_per_branch()

	def _validate_unique_buzzer_per_branch(self):
		"""Đảm bảo không có 2 buzzer có cùng số trong 1 branch."""
		existing = frappe.db.exists(
			"Leescoffee Buzzer",
			{
				"buzzer_number": self.buzzer_number,
				"branch": self.branch,
				"name": {"!=": self.name},
			},
		)
		if existing:
			frappe.throw(
				_("Buzzer số {0} đã tồn tại trong chi nhánh {1}."),
				params=[self.buzzer_number, self.branch],
			)

	@staticmethod
	def get_available_buzzer(branch):
		"""Trả về 1 buzzer 'Sẵn sàng' trong branch, hoặc None nếu không có."""
		return frappe.db.get_value(
			"Leescoffee Buzzer",
			{"status": "Sẵn sàng", "branch": branch},
			"name",
		)

	@staticmethod
	def set_busy(buzzer_name, pos_invoice_name):
		"""Đánh dấu buzzer là 'Đang dùng' và gán cho POS Invoice."""
		buzzer = frappe.get_doc("Leescoffee Buzzer", buzzer_name)
		if buzzer.status != "Sẵn sàng":
			frappe.throw(
				_("Buzzer {0} không ở trạng thái Sẵn sàng.").format(buzzer_name)
			)
		buzzer.status = "Đang dùng"
		buzzer.save(ignore_permissions=True)

	@staticmethod
	def set_available(buzzer_name):
		"""Reset buzzer về 'Sẵn sàng' sau khi đơn xong."""
		buzzer = frappe.get_doc("Leescoffee Buzzer", buzzer_name)
		buzzer.status = "Sẵn sàng"
		buzzer.save(ignore_permissions=True)