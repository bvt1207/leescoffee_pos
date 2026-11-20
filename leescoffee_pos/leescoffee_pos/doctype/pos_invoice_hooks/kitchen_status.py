"""Trạng thái pha chế (POS Invoice.custom_kitchen_status) — MỘT nơi cho hằng, đơn dở của ca và kết thúc đơn.

Dùng bởi: pos_api (set_kitchen_status, resolve_open_order(s), force_close_shift, giữ thẻ rung), pos_invoice_hooks (nhả thẻ rung),
pos_shift_hooks (chặn đóng ca), customer_order_api (stage của khách QR). Quy tắc: .claude/rules/leescoffee_pos/pos_invoice_hooks.md.

Vòng đời (2026-11-20): (trống) -> Chưa làm -> Đã làm -> Đã hoàn thành; hoặc kết thúc có lý do:
"Khách không nhận", "Không thực hiện được" (thu ngân / quản lý), "Đã đóng ca chưa xử lý" (đóng ca bắt buộc).
Trạng thái kết thúc = không còn giữ thẻ rung, không chặn đóng ca. Ba trạng thái kết thúc mới bật `needs_review` cho quản lý xem lại.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

KS_TODO = "Chưa làm"
KS_PREPARED = "Đã làm"
KS_COMPLETED = "Đã hoàn thành"
OUTCOME_NOT_PICKED = "Khách không nhận"
OUTCOME_FAILED = "Không thực hiện được"
SHIFT_CLOSED = "Đã đóng ca chưa xử lý"

# Bước tiến của màn pha chế (set_kitchen_status đi từng bước theo danh sách này).
KITCHEN_FLOW = [KS_TODO, KS_PREPARED, KS_COMPLETED]
# Đơn đã thanh toán ở các trạng thái này chặn đóng ca ("đơn dở").
KITCHEN_BLOCK_STATUSES = [KS_TODO, KS_PREPARED]
# Trạng thái kết thúc: không giữ thẻ rung, không chặn đóng ca.
KITCHEN_TERMINAL_STATUSES = [KS_COMPLETED, OUTCOME_NOT_PICKED, OUTCOME_FAILED, SHIFT_CLOSED]
# Kết quả thu ngân / quản lý được chọn khi xử lý đơn dở (resolve_open_order).
RESOLVE_OUTCOMES = [KS_COMPLETED, OUTCOME_NOT_PICKED, OUTCOME_FAILED]
# Kết thúc bất thường -> needs_review = 1 (hoàn tiền / hao hụt).
NEEDS_REVIEW_STATUSES = [OUTCOME_NOT_PICKED, OUTCOME_FAILED, SHIFT_CLOSED]
# Thứ tự options của Custom Field Select (fixtures + patch v1_kitchen_outcomes).
KITCHEN_STATUS_OPTIONS = [KS_TODO, KS_PREPARED, KS_COMPLETED, OUTCOME_NOT_PICKED, OUTCOME_FAILED, SHIFT_CLOSED]

LIST_LIMIT = 10  # số mã đơn liệt kê mỗi nhóm trong thông báo chặn đóng ca


def is_terminal(status):
	return (status or "") in KITCHEN_TERMINAL_STATUSES


# --- Đơn dở của ca --------------------------------------------------------------------------------


def shift_open_orders(pos_profile, period_start=None):
	"""Đơn dở của ca: {drafts, unprepared, undelivered} (danh sách mã đơn).

	- drafts: order_cancel.closing_blockers (Draft kênh khác QR + Draft QR còn hạn thanh toán).
	- unprepared / undelivered: POS Invoice đã thanh toán của ca — cùng POS Profile, Timestamp(posting_date, posting_time)
	  >= period_start (như màn Orders), docstatus 1, status Paid, chưa gộp (consolidated_invoice rỗng), không phải trả hàng;
	  custom_kitchen_status "Chưa làm" (kể cả rỗng — dữ liệu cũ) / "Đã làm".
	"""
	from frappe.query_builder import DocType
	from frappe.query_builder import functions as fn

	from ..mypos_order_cancel_log.order_cancel import closing_blockers

	result = {"drafts": closing_blockers(pos_profile), "unprepared": [], "undelivered": []}
	if not pos_profile:
		return result
	inv = DocType("POS Invoice")
	cond = (
		(inv.pos_profile == pos_profile)
		& (inv.docstatus == 1)
		& (inv.status == "Paid")
		& (fn.IfNull(inv.consolidated_invoice, "") == "")
		& (fn.IfNull(inv.is_return, 0) == 0)
		& fn.IfNull(inv.custom_kitchen_status, "").isin(["", *KITCHEN_BLOCK_STATUSES])
	)
	if period_start:
		cond &= fn.Timestamp(inv.posting_date, inv.posting_time) >= period_start
	rows = (
		frappe.qb.from_(inv)
		.select(inv.name, inv.custom_kitchen_status)
		.where(cond)
		.orderby(inv.creation)
		.run(as_dict=True)
	)
	for r in rows:
		key = "undelivered" if r.custom_kitchen_status == KS_PREPARED else "unprepared"
		result[key].append(r.name)
	return result


def has_open_orders(groups):
	return any(groups.get(k) for k in ("drafts", "unprepared", "undelivered"))


def _list(names):
	shown = ", ".join(names[:LIST_LIMIT])
	more = len(names) - LIST_LIMIT
	return shown + (_(" và {0} đơn khác").format(more) if more > 0 else "")


def open_orders_message(groups):
	"""Thông báo chặn đóng ca, mỗi nhóm tối đa LIST_LIMIT mã."""
	parts = []
	if groups.get("drafts"):
		parts.append(_("{0} đơn chưa thanh toán: {1}").format(len(groups["drafts"]), _list(groups["drafts"])))
	if groups.get("unprepared"):
		parts.append(_("{0} đơn đã thanh toán, chưa pha chế: {1}").format(len(groups["unprepared"]), _list(groups["unprepared"])))
	if groups.get("undelivered"):
		parts.append(_("{0} đơn đã làm, chưa giao: {1}").format(len(groups["undelivered"]), _list(groups["undelivered"])))
	return _(
		"Chưa đóng được ca. Còn {0}. Thu tiền / hủy đơn chưa thanh toán và giao hoặc kết thúc đơn dở (có lý do) trước khi đóng ca "
		"(quản lý có thể dùng Đóng ca bắt buộc)."
	).format("; ".join(parts))


# --- Kết thúc đơn ---------------------------------------------------------------------------------


def set_terminal(invoice, outcome, reason=None, note=None):
	"""Đặt trạng thái kết thúc cho đơn đã thanh toán (doc POS Invoice): người/giờ kết thúc, lý do, needs_review, comment.

	save() -> hook on_update_after_submit nhả thẻ rung (trạng thái kết thúc). Không commit (giao dịch của người gọi).
	"""
	if outcome not in KITCHEN_TERMINAL_STATUSES:
		frappe.throw(_("Trạng thái kết thúc không hợp lệ: {0}.").format(outcome))
	actor = frappe.session.user
	text = "; ".join(x.strip() for x in (reason or "", note or "") if x and x.strip())
	previous = invoice.custom_kitchen_status or KS_TODO
	invoice.custom_kitchen_status = outcome
	invoice.kitchen_completed_by = actor
	invoice.kitchen_completed_at = now_datetime()
	invoice.kitchen_outcome_reason = text or None
	invoice.needs_review = 1 if outcome in NEEDS_REVIEW_STATUSES else 0
	invoice.save(ignore_permissions=True)
	invoice.add_comment(
		"Info",
		_("Kết thúc đơn: {0} → {1}{2}. Bởi {3}.").format(
			previous, outcome, (_(". Lý do: {0}").format(text) if text else ""), actor
		),
	)
	return invoice
