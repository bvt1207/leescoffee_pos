import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate


class LeescoffeeMenu(Document):
    """Quản lý menu và danh sách món dùng cho POS."""

    def validate(self):
        if not self.items:
            frappe.throw(
                _("Menu {0} phải có ít nhất 1 món.").format(
                    self.menu_name or self.name
                )
            )

        # Đồng bộ lại thông tin từng món trước khi lưu Menu.
        for row in self.items:
            row.load_item_details(parent_doc=self)

    @staticmethod
    def get_menu_with_items(price_list=None):
        """Lấy danh sách menu kèm các món đã cấu hình."""
        filters = {}
        if price_list:
            filters["price_list"] = price_list

        menus = frappe.get_all(
            "Leescoffee Menu",
            filters=filters,
            fields=["name", "menu_name", "price_list"],
        )

        result = []

        for menu in menus:
            items = frappe.get_all(
                "Leescoffee Menu Item",
                filters={
                    "parent": menu.name,
                    "parenttype": "Leescoffee Menu",
                    "parentfield": "items",
                },
                fields=[
                    "idx",
                    "item_code",
                    "item_name",
                    "item_type",
                    "price",
                ],
                order_by="idx asc",
            )

            result.append(
                {
                    "name": menu.name,
                    "menu_name": menu.menu_name,
                    "price_list": menu.price_list,
                    "items": items,
                }
            )

        return result

    @staticmethod
    def get_price_for_item(item_code, price_list):
        """Lấy giá bán có hiệu lực theo Item và Price List."""
        if not item_code or not frappe.db.exists("Item", item_code):
            frappe.throw(
                _("Item {0} không tồn tại.").format(item_code or "")
            )

        if not price_list:
            return None

        item = frappe.db.get_value(
            "Item",
            item_code,
            ["disabled", "has_variants", "variant_of"],
            as_dict=True,
        )

        if item.disabled:
            frappe.throw(
                _("Item {0} đã bị vô hiệu hóa.").format(item_code)
            )

        # Item Template không có giá bán trực tiếp.
        if item.has_variants and not item.variant_of:
            return None

        today = getdate(nowdate())

        item_prices = frappe.get_all(
            "Item Price",
            filters={
                "item_code": item_code,
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

            return float(item_price.price_list_rate or 0)

        return None