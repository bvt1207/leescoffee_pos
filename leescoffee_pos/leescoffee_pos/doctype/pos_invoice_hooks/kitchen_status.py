"""Trạng thái pha chế (POS Invoice.custom_kitchen_status) — MỘT nơi cho hằng, đơn dở của ca và kết thúc đơn.

Dùng bởi: pos_api (set_kitchen_status, resolve_open_order, giữ thẻ bàn), pos_invoice_hooks (nhả thẻ bàn),
pos_shift_hooks (chặn đóng ca), customer_order_api (stage của khách QR), sepay (báo tiền về sau khi hủy).
Quy tắc: .claude/rules/leescoffee_pos/pos_invoice_hooks.md.

Vòng đời (2026-11-20): (trống) -> Chưa làm -> Đã làm -> Đã hoàn thành; hoặc kết thúc có lý do:
"Khách không nhận", "Không thực hiện được" (thu ngân / quản lý xử lý từng đơn, lý do ở kitchen_outcome_reason).
Trạng thái kết thúc = không còn giữ thẻ bàn, không chặn đóng ca. 2026-11-23: bỏ cờ needs_review, "Đã đóng ca chưa xử lý",
hàng đợi "Cần xử lý" (patch v1_simplify_cancel_review dọn dữ liệu cũ).
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

KS_TODO = "Chưa làm"
KS_PREPARED = "Đã làm"
KS_COMPLETED = "Đã hoàn thành"
OUTCOME_NOT_PICKED = "Khách không nhận"
OUTCOME_FAILED = "Không thực hiện được"
# Giá trị cũ (đóng ca bắt buộc, đã bỏ 2026-11-23): chỉ còn để patch v1_simplify_cancel_review dọn dữ liệu.
LEGACY_SHIFT_CLOSED = "Đã đóng ca chưa xử lý"

# Bước tiến của màn pha chế (set_kitchen_status đi từng bước theo danh sách này).
KITCHEN_FLOW = [KS_TODO, KS_PREPARED, KS_COMPLETED]
# Đơn đã thanh toán ở các trạng thái này chặn đóng ca ("đơn dở").
KITCHEN_BLOCK_STATUSES = [KS_TODO, KS_PREPARED]
# Trạng thái kết thúc: không giữ thẻ bàn, không chặn đóng ca.
KITCHEN_TERMINAL_STATUSES = [KS_COMPLETED, OUTCOME_NOT_PICKED, OUTCOME_FAILED]
# Kết quả thu ngân / quản lý được chọn khi xử lý đơn dở (resolve_open_order).
RESOLVE_OUTCOMES = [KS_COMPLETED, OUTCOME_NOT_PICKED, OUTCOME_FAILED]
# Thứ tự options của Custom Field Select (fixtures + patch v1_kitchen_outcomes).
KITCHEN_STATUS_OPTIONS = [KS_TODO, KS_PREPARED, KS_COMPLETED, OUTCOME_NOT_PICKED, OUTCOME_FAILED]

MANAGER_ROLE = "POS MANAGER"
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

	from .order_cancel import closing_blockers

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
		"Chưa đóng được ca. Còn {0}. Thu tiền / hủy đơn chưa thanh toán và giao hoặc kết thúc đơn dở (có lý do) trước khi đóng ca."
	).format("; ".join(parts))


# --- Kết thúc đơn ---------------------------------------------------------------------------------


def set_terminal(invoice, outcome, reason=None, note=None):
	"""Đặt trạng thái kết thúc cho đơn đã thanh toán (doc POS Invoice): người/giờ kết thúc, lý do, comment.

	save() -> hook on_update_after_submit nhả thẻ bàn (trạng thái kết thúc). Không commit (giao dịch của người gọi).
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
	invoice.save(ignore_permissions=True)
	invoice.add_comment(
		"Info",
		_("Kết thúc đơn: {0} → {1}{2}. Bởi {3}.").format(
			previous, outcome, (_(". Lý do: {0}").format(text) if text else ""), actor
		),
	)
	return invoice


# --- Thông báo cho quản lý của chi nhánh ----------------------------------------------------------


def profile_managers(pos_profile):
	"""User đang bật, có role POS MANAGER, thuộc Applicable for Users của POS Profile."""
	if not pos_profile:
		return []
	users = frappe.get_all(
		"POS Profile User",
		filters={"parent": pos_profile, "parenttype": "POS Profile", "parentfield": "applicable_for_users"},
		pluck="user",
	)
	out = []
	for user in dict.fromkeys(u for u in users if u):
		if frappe.db.get_value("User", user, "enabled") and MANAGER_ROLE in frappe.get_roles(user):
			out.append(user)
	return out


def all_managers():
	users = frappe.get_all("Has Role", filters={"role": MANAGER_ROLE, "parenttype": "User"}, pluck="parent")
	return [u for u in dict.fromkeys(users) if frappe.db.get_value("User", u, "enabled")]


def notify_users(users, subject, document_type=None, document_name=None):
	for user in users:
		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"subject": subject,
				"for_user": user,
				"type": "Alert",
				"document_type": document_type,
				"document_name": document_name,
			}
		).insert(ignore_permissions=True)
	return list(users)


def notify_profile_managers(pos_profile, subject, document_type=None, document_name=None, fallback_all=False):
	"""Gửi Notification Log cho quản lý của chi nhánh (không gửi toàn bộ). fallback_all: không có ai -> mọi POS MANAGER."""
	users = profile_managers(pos_profile)
	if not users and fallback_all:
		users = all_managers()
	return notify_users(users, subject, document_type, document_name)
