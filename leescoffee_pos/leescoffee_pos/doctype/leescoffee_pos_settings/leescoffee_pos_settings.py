import frappe
from frappe import _
from frappe.model.document import Document


class LeescoffeePOSSettings(Document):
	"""Cấu hình toàn cục cho module POS Leescoffee."""

	def validate(self):
		"""Kiểm tra dữ liệu khi lưu."""
		self._validate_sepay_config()

	def _validate_sepay_config(self):
		"""Nếu bật SePay, các trường API bắt buộc phải được nhập."""
		if self.sepay_enabled:
			required_fields = {
				"sepay_merchant_code": "Mã merchant",
				"sepay_api_key": "API Key",
				"sepay_secret_key": "Secret Key",
			}
			for fieldname, label in required_fields.items():
				if not getattr(self, fieldname, None):
					frappe.throw(
						_("{0} là bắt buộc khi bật SePay"),
						title=_("Thiếu cấu hình SePay"),
					)
					# Re-raise để dừng validate
					frappe.throw(_(f"{label} không được để trống khi SePay được kích hoạt."))

	@staticmethod
	def get_brand_info():
		"""
		Lấy thông tin thương hiệu từ cài đặt chung.
		Trả về dict chứa: brand_name, brand_logo, brand_banner, brand_phone, brand_address.
		Dùng bởi frontend POS và hóa đơn để hiển thị branding tĩnh.
		"""
		settings = frappe.get_single("Leescoffee POS Settings")
		return {
			"brand_name": settings.brand_name or "",
			"brand_logo": settings.brand_logo or "",
			"brand_banner": settings.brand_banner or "",
			"brand_phone": settings.brand_phone or "",
			"brand_address": settings.brand_address or "",
		}

	@staticmethod
	def get_sepay_config():
		"""
		Lấy cấu hình SePay. Trả về dict hoặc None nếu chưa bật.
		"""
		settings = frappe.get_single("Leescoffee POS Settings")
		if not settings.sepay_enabled:
			return None
		return {
			"merchant_code": settings.sepay_merchant_code,
			"api_key": settings.sepay_api_key,
			"secret_key": settings.sepay_secret_key,
			"env": settings.sepay_env or "sandbox",
			"callback_url": settings.sepay_callback_url or "",
		}

	@staticmethod
	def get_default_branch():
		"""Trả về chi nhánh mặc định từ cài đặt."""
		settings = frappe.get_single("Leescoffee POS Settings")
		return settings.default_branch or None
