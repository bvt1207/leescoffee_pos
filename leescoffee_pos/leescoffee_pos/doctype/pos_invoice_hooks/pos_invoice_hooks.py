
"""
Hooks for POS Invoice DocType to handle Leescoffee POS business logic.

- Khởi tạo custom_kitchen_status khi invoice đã thanh toán.
- Buzzer Dine In chuyển sang Đang dùng khi invoice đã Paid và submit.
- Thẻ bàn (MYPOS Buzzer) tự về Sẵn sàng khi đơn kết thúc (Đã hoàn thành / Khách không nhận / Không thực hiện được)
  hoặc bị hủy, nếu không còn hóa đơn Dine In khác giữ thẻ. Không có bước nhả thẻ thủ công.
"""

import frappe
from frappe import _
from frappe.utils import flt

# Trạng thái kết thúc (Đã hoàn thành + kết thúc có lý do) không giữ thẻ bàn — kitchen_status.py.
from .kitchen_status import KITCHEN_TERMINAL_STATUSES, is_terminal


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
                "MYPOS Buzzer",
                doc.buzzer,
                "status",
            )

            if buzzer_status == "Sẵn sàng":
                from leescoffee_pos.leescoffee_pos.doctype.mypos_buzzer.mypos_buzzer import (
                    MYPOSBuzzer,
                )

                MYPOSBuzzer.set_busy(doc.buzzer, doc.name)

            elif buzzer_status == "Đang dùng":
                # Buzzer đã được sử dụng; không tự đổi trạng thái tại đây.
                pass
            else:
                frappe.throw(
                    _("Thẻ bàn {0} không ở trạng thái Sẵn sàng.").format(
                        doc.buzzer
                    )
                )

        # Đơn có đổi điểm: ghi dòng Loyalty Point Entry âm (ERPNext đã tự ghi dòng tích).
        if flt(doc.get("redeemed_points")) > 0:
            from leescoffee_pos.leescoffee_pos.api.pos_api import _record_redemption

            _record_redemption(doc)

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
            or not is_terminal(doc.custom_kitchen_status)
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
                "custom_kitchen_status": ["not in", KITCHEN_TERMINAL_STATUSES],
            },
            fields=["name"],
            limit=1,
        )

        if other_invoices:
            return

        buzzer = frappe.get_doc(
            "MYPOS Buzzer",
            doc.buzzer,
        )

        if buzzer.status == "Đang dùng":
            buzzer.status = "Sẵn sàng"
            buzzer.save(ignore_permissions=True)

    @staticmethod
    def _free_buzzer_if_unheld(doc):
        """Trả thẻ về Sẵn sàng nếu không còn đơn Dine In đã thanh toán khác chưa kết thúc giữ cùng thẻ."""
        other_invoices = frappe.get_all(
            "POS Invoice",
            filters={
                "name": ["!=", doc.name],
                "docstatus": 1,
                "status": "Paid",
                "order_type": "Dine In",
                "buzzer": doc.buzzer,
                "custom_kitchen_status": ["not in", KITCHEN_TERMINAL_STATUSES],
            },
            fields=["name"],
            limit=1,
        )
        if other_invoices:
            return

        buzzer = frappe.get_doc("MYPOS Buzzer", doc.buzzer)
        if buzzer.status == "Đang dùng":
            buzzer.status = "Sẵn sàng"
            buzzer.save(ignore_permissions=True)

    @staticmethod
    def release_buzzer(doc, method=None):
        """Nhả thẻ cho đơn đã kết thúc mà không qua save() (vd. đơn đã gộp, pos_api._resolve_consolidated).

        Không có bước "đã phục vụ" / "khách đã lấy" thủ công (2026-11-23): đơn kết thúc là thẻ tự nhả.
        """
        if (
            doc.order_type != "Dine In"
            or not doc.buzzer
            or not is_terminal(doc.custom_kitchen_status)
        ):
            return
        PosInvoiceHooks._free_buzzer_if_unheld(doc)

    @staticmethod
    def on_cancel(doc, method=None):
        """
        Đơn đã submit bị hủy: không còn giữ thẻ, ở MỌI trạng thái pha chế (2026-11-23; trước chỉ khi chưa làm).
        """
        if doc.order_type != "Dine In" or not doc.buzzer:
            return
        PosInvoiceHooks._free_buzzer_if_unheld(doc)


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
                "MYPOS Buzzer",
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
