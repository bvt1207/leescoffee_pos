import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate


class LeescoffeeMenuItem(Document):
    """Child DocType lưu các món thuộc Leescoffee Menu."""

    def validate(self):
        self.load_item_details()

    def load_item_details(self, parent_doc=None):
        """Đồng bộ thông tin Item và giá bán từ Price List của Menu."""
        if not self.item_code:
            self.item_name = None
            self.item_type = None
            self.price = None
            return

        parent = parent_doc or self.get_parent_doc()

        self.load_item_info()

        if parent and parent.price_list:
            self.load_item_price(parent.price_list)
        else:
            self.price = None

    def get_parent_doc(self):
        """Lấy document cha, xử lý cả trường hợp parent_doc là weakref."""
        parent_doc = getattr(self, "parent_doc", None)

        # Một số phiên bản Frappe có thể trả về weak reference.
        if callable(parent_doc):
            try:
                parent_doc = parent_doc()
            except TypeError:
                parent_doc = None

        if parent_doc and hasattr(parent_doc, "price_list"):
            return parent_doc

        if not self.parent:
            return None

        if self.parenttype != "Leescoffee Menu":
            return None

        try:
            return frappe.get_doc("Leescoffee Menu", self.parent)
        except frappe.DoesNotExistError:
            return None

    def load_item_info(self):
        """Lấy tên và loại hàng từ ERPNext Item."""
        if not frappe.db.exists("Item", self.item_code):
            frappe.throw(
                _("Item {0} không tồn tại. Vui lòng chọn Item có sẵn.").format(
                    self.item_code
                )
            )

        item = frappe.get_doc("Item", self.item_code)

        if item.disabled:
            frappe.throw(
                _("Item {0} đã bị vô hiệu hóa.").format(self.item_code)
            )

        self.item_name = item.item_name or item.item_code
        self.item_type = "Stock" if item.is_stock_item else "Service"

    def load_item_price(self, price_list):
        """Lấy giá từ Item Price theo Price List, chỉ lấy giá còn hiệu lực."""
        if not self.item_code or not price_list:
            self.price = None
            return

        item_doc = frappe.db.get_value(
            "Item",
            self.item_code,
            ["disabled", "has_variants", "variant_of"],
            as_dict=True,
        )

        if not item_doc:
            frappe.throw(
                _("Item {0} không tồn tại.").format(self.item_code)
            )

        if item_doc.disabled:
            frappe.throw(
                _("Item {0} đã bị vô hiệu hóa.").format(self.item_code)
            )

        # Template không lấy giá; Variant lấy giá theo chính item_code.
        is_template = item_doc.has_variants and not item_doc.variant_of
        if is_template:
            self.price = None
            return

        today = getdate(nowdate())

        item_prices = frappe.get_all(
            "Item Price",
            filters={
                "item_code": self.item_code,
                "price_list": price_list,
                "selling": 1,
                "currency": "VND",
            },
            fields=["price_list_rate", "valid_from", "valid_upto"],
            order_by="valid_from desc",
        )

        for item_price in item_prices:
            valid_from = (
                getdate(item_price.valid_from)
                if item_price.valid_from
                else None
            )
            valid_upto = (
                getdate(item_price.valid_upto)
                if item_price.valid_upto
                else None
            )

            if valid_from and valid_from > today:
                continue

            if valid_upto and valid_upto < today:
                continue

            self.price = float(item_price.price_list_rate or 0)
            return

        # Không tìm thấy giá phù hợp thì để trống, tránh hiển thị sai giá.
        self.price = None