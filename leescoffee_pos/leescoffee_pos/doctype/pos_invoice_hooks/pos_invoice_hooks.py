
"""
Hooks for POS Invoice DocType to handle Leescoffee POS business logic.

- Khởi tạo custom_kitchen_status khi invoice đã thanh toán.
- Buzzer Dine In chuyển sang Đang dùng khi invoice đã Paid và submit.
- Thẻ bàn (MYPOS Buzzer) tự về Sẵn sàng khi đơn kết thúc (Đã hoàn thành / Khách không nhận / Không thực hiện được)
  hoặc bị hủy, nếu không còn hóa đơn Dine In khác giữ thẻ. Không có bước nhả thẻ thủ công.
- payment_status (Custom Field "Trạng thái thanh toán", 2026-11-25): MỘT nơi tính theo trạng thái đơn —
  before_submit -> "Đã thanh toán" (mọi đường: tiền mặt, webhook SePay, submit tay trên Desk, đơn QR);
  on_cancel -> "Hủy". Đơn trả hàng (is_return) không đụng. Hủy đơn nháp (order_cancel.cancel_draft, không qua hook)
  ghi "Hủy" trong cùng set_value. Sinh QR (sepay.generate_qr_for_invoice) ghi "Đang chờ".
"""

import frappe
from frappe import _
from frappe.utils import cint, flt

# Trạng thái kết thúc (Đã hoàn thành + kết thúc có lý do) không giữ thẻ bàn — kitchen_status.py.
from .kitchen_status import KITCHEN_TERMINAL_STATUSES, is_terminal

# Giá trị Select của POS Invoice.payment_status (fixtures/custom_field.json) — dùng chung, không gõ lại chuỗi.
PAYMENT_UNPAID = "Chưa thanh toán"
PAYMENT_WAITING = "Đang chờ"
PAYMENT_PAID = "Đã thanh toán"
PAYMENT_CANCELLED = "Hủy"


class PosInvoiceHooks:

    @staticmethod
    def before_submit(doc, method=None):
        """Đơn bán (không phải trả hàng) được submit = đã thu đủ tiền -> "Đã thanh toán".

        Gán trên doc trước khi ghi DB: không thêm lần ghi, hiện trong Version của lần submit.
        """
        if cint(doc.get("is_return")):
            return
        doc.payment_status = PAYMENT_PAID

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

        # Màn khách (/pos/customer) đang hiện đơn này -> "Thanh toán thành công" (sau commit, lỗi không chặn submit).
        from leescoffee_pos.leescoffee_pos.api.customer_display_api import touch_paid

        touch_paid(doc)

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
        Đơn đã submit bị hủy: payment_status -> "Hủy" (không đụng đơn trả hàng); không còn giữ thẻ, ở MỌI trạng thái
        pha chế (2026-11-23; trước chỉ khi chưa làm).
        """
        if not cint(doc.get("is_return")) and doc.get("payment_status") != PAYMENT_CANCELLED:
            doc.db_set("payment_status", PAYMENT_CANCELLED, update_modified=False)
        if doc.order_type != "Dine In" or not doc.buzzer:
            return
        PosInvoiceHooks._free_buzzer_if_unheld(doc)


def before_submit(doc, method=None):
    return PosInvoiceHooks.before_submit(doc, method)


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
            "pos_profile",
            "order_type",
            "custom_kitchen_status",
            "buzzer",
            "creation",
        ],
        order_by="creation asc",
    )

    from leescoffee_pos.leescoffee_pos.doctype.pos_profile_hooks.pos_profile_hooks import walk_in_by_profile

    walk_ins = walk_in_by_profile([inv.pos_profile for inv in invoices])
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
            # Khách vãng lai theo POS Profile của đơn (2026-11-24) — giao diện không so tên Customer.
            "is_walk_in": bool(walk_ins.get(inv.pos_profile)) and inv.customer == walk_ins.get(inv.pos_profile),
            "order_type": inv.order_type,
            "kitchen_status": inv.custom_kitchen_status,
            "buzzer_number": buzzer_number,
            "last_updated": inv.creation,
        })

    return result
