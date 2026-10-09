import frappe
from frappe import _
from frappe.model.document import Document


class LeescoffeePOSSettings(Document):
	"""Cấu hình toàn/module POS Leescoffee."""

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
	def get_default_branch():
		"""Trả về chi nhánh mặc định từ cài đặt."""
		settings = frappe.get_single("Leescoffee POS Settings")
		return settings.default_branch or None