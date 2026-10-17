
"""
Hooks for POS Invoice DocType to handle Leescoffee POS business logic.

- Khởi tạo custom_kitchen_status khi invoice đã thanh toán.
- Buzzer Dine In chuyển sang Đang dùng khi invoice đã Paid và submit.
- Phase 3: Reset Buzzer về Sẵn sàng khi pha chế hoàn thành
  và không còn hóa đơn Dine In khác đang sử dụng Buzzer.
- Huỷ đơn trước khi bắt đầu làm có thể reset Buzzer.
"""

import frappe
from frappe import _


class PosInvoiceHooks:

    @staticmethod
    def on_submit(doc, method=None):
        """
        Khi POS Invoice được submit:
        1. Khởi tạo trạng thái pha chế nếu đơn đã Paid.
        2. Giữ Buzzer cho đơn Dine In đã thanh toán.
        """
        if doc.status == "Paid" and not doc.custom_kitchen_status:
            doc.custom_kitchen_status = "Chưa làm"
            doc.db_set(
                "custom_kitchen_status",
                "Chưa làm",
                update_modified=False,
            )

        if (
            doc.docstatus == 1
            and doc.status == "Paid"
            and doc.order_type == "Dine In"
            and doc.buzzer
        ):
            buzzer_status = frappe.db.get_value(
                "Leescoffee Buzzer",
                doc.buzzer,
                "status",
            )

            if buzzer_status == "Sẵn sàng":
                from leescoffee_pos.leescoffee_pos.doctype.leescoffee_buzzer.leescoffee_buzzer import (
                    LeescoffeeBuzzer,
                )

                LeescoffeeBuzzer.set_busy(doc.buzzer, doc.name)

            elif buzzer_status == "Đang dùng":
                # Buzzer đã được sử dụng; không tự đổi trạng thái tại đây.
                pass
            else:
                frappe.throw(
                    _("Buzzer {0} không ở trạng thái Sẵn sàng.").format(
                        doc.buzzer
                    )
                )

    @staticmethod
    def before_save(doc, method=None):
        """
        Chừa hook cho các quy tắc kiểm tra trước khi lưu.
        """
        pass

    @staticmethod
    def on_update_after_submit(doc, method=None):
        """
        Phase 3:
        Khi trạng thái pha chế là Đã hoàn thành,
        reset Buzzer nếu không còn hóa đơn Dine In khác
        chưa hoàn thành đang sử dụng Buzzer đó.
        """
        if (
            doc.docstatus != 1
            or doc.status != "Paid"
            or doc.order_type != "Dine In"
            or not doc.buzzer
            or doc.custom_kitchen_status != "Đã hoàn thành"
        ):
            return

        # Tìm hóa đơn Dine In khác còn chưa hoàn thành
        # và đang sử dụng cùng Buzzer.
        other_invoices = frappe.get_all(
            "POS Invoice",
            filters={
                "name": ["!=", doc.name],
                "docstatus": 1,
                "status": "Paid",
                "order_type": "Dine In",
                "buzzer": doc.buzzer,
                "custom_kitchen_status": ["!=", "Đã hoàn thành"],
            },
            fields=["name"],
            limit=1,
        )

        if other_invoices:
            return

        buzzer = frappe.get_doc(
            "Leescoffee Buzzer",
            doc.buzzer,
        )

        if buzzer.status == "Đang dùng":
            buzzer.status = "Sẵn sàng"
            buzzer.save(ignore_permissions=True)

    @staticmethod
    def confirm_pickup(doc, method=None):
        """
        Giữ lại phương thức xác nhận khách lấy món.
        Chỉ reset khi trạng thái pha chế là Đã hoàn thành.
        """
        if (
            doc.order_type != "Dine In"
            or not doc.buzzer
            or doc.custom_kitchen_status != "Đã hoàn thành"
        ):
            return

        # Tránh reset nếu hóa đơn khác vẫn cần dùng Buzzer.
        other_invoices = frappe.get_all(
            "POS Invoice",
            filters={
                "name": ["!=", doc.name],
                "docstatus": 1,
                "status": "Paid",
                "order_type": "Dine In",
                "buzzer": doc.buzzer,
                "custom_kitchen_status": ["!=", "Đã hoàn thành"],
            },
            fields=["name"],
            limit=1,
        )

        if other_invoices:
            return

        buzzer = frappe.get_doc(
            "Leescoffee Buzzer",
            doc.buzzer,
        )

        if buzzer.status == "Đang dùng":
            buzzer.status = "Sẵn sàng"
            buzzer.save(ignore_permissions=True)

            frappe.msgprint(
                _("Buzzer {0} đã trở về trạng thái Sẵn sàng.").format(
                    doc.buzzer
                )
            )

    @staticmethod
    def on_cancel(doc, method=None):
        """
        Khi hủy invoice, chỉ reset Buzzer nếu đơn chưa bắt đầu làm.
        """
        if (
            doc.order_type != "Dine In"
            or not doc.buzzer
            or doc.custom_kitchen_status not in (None, "", "Chưa làm")
        ):
            return

        # Không reset nếu hóa đơn khác vẫn đang sử dụng Buzzer.
        other_invoices = frappe.get_all(
            "POS Invoice",
            filters={
                "name": ["!=", doc.name],
                "docstatus": 1,
                "status": "Paid",
                "order_type": "Dine In",
                "buzzer": doc.buzzer,
                "custom_kitchen_status": ["!=", "Đã hoàn thành"],
            },
            fields=["name"],
            limit=1,
        )

        if other_invoices:
            return

        buzzer = frappe.get_doc(
            "Leescoffee Buzzer",
            doc.buzzer,
        )

        if buzzer.status == "Đang dùng":
            buzzer.status = "Sẵn sàng"
            buzzer.save(ignore_permissions=True)


def on_submit(doc, method=None):
    return PosInvoiceHooks.on_submit(doc, method)


def before_save(doc, method=None):
    return PosInvoiceHooks.before_save(doc, method)


def on_update_after_submit(doc, method=None):
    return PosInvoiceHooks.on_update_after_submit(doc, method)


def on_cancel(doc, method=None):
    return PosInvoiceHooks.on_cancel(doc, method)


@frappe.whitelist()
def get_status_board_orders():
    """
    Lấy danh sách POS Invoice đã submit, Paid và có trạng thái pha chế.
    """
    invoices = frappe.get_all(
        "POS Invoice",
        filters={
            "docstatus": 1,
            "status": "Paid",
            "custom_kitchen_status": ["!=", ""],
        },
        fields=[
            "name",
            "customer",
            "order_type",
            "custom_kitchen_status",
            "buzzer",
            "creation",
        ],
        order_by="creation asc",
    )

    result = []

    for inv in invoices:
        customer_name = ""

        if inv.customer:
            customer_name = (
                frappe.db.get_value(
                    "Customer",
                    inv.customer,
                    "customer_name",
                )
                or inv.customer
            )

        buzzer_number = None

        if inv.buzzer:
            buzzer_number = frappe.db.get_value(
                "Leescoffee Buzzer",
                inv.buzzer,
                "buzzer_number",
            )

        result.append({
            "invoice_name": inv.name,
            "customer_name": customer_name,
            "order_type": inv.order_type,
            "kitchen_status": inv.custom_kitchen_status,
            "buzzer_number": buzzer_number,
            "last_updated": inv.creation,
        })

    return result
