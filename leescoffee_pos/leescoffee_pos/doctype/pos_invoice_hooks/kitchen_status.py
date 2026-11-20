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


# --- Đơn cần quản lý xử lý ("Cần xử lý") ----------------------------------------------------------
# Đơn đã submit (Paid hoặc đã gộp khi đóng ca), không phải trả hàng, đang "Đã đóng ca chưa xử lý" hoặc needs_review = 1.
# Không lọc theo ca / ngày / consolidated. Quản lý xử lý trên Desk (2026-11-21, máy POS không đổi): Script Report
# "MYPOS Review Queue" + nút "Xử lý đơn" trên form POS Invoice (public/js/pos_invoice.js) -> pos_api.resolve_open_order;
# job remind_overdue_reviews nhắc qua Notification Log.
REVIEW_OVERDUE_HOURS = 24  # quá số giờ này (tính từ lúc tạo đơn) -> "quá hạn" (cột Report, job nhắc)
REVIEW_REMIND_HOURS = 24  # đơn đã có Notification Log trong khoảng này -> job không nhắc lại
REVIEW_OUTCOMES = [KS_COMPLETED, OUTCOME_FAILED, OUTCOME_NOT_PICKED]  # kết cục quản lý chọn khi xử lý
REVIEW_REMIND_PREFIX = "[Cần xử lý]"  # tiền tố tiêu đề Notification Log của job nhắc
MANAGER_ROLE = "POS MANAGER"


def needs_manager_review(status, needs_review):
	"""Đơn thuộc hàng đợi "Cần xử lý"."""
	return (status or "") == SHIFT_CLOSED or bool(frappe.utils.cint(needs_review))


def _review_cond(inv, pos_profile=None, search=None, overdue_only=False):
	from frappe.query_builder import functions as fn
	from frappe.utils import add_to_date

	cond = (
		(inv.docstatus == 1)
		& (fn.IfNull(inv.is_return, 0) == 0)
		& ((inv.custom_kitchen_status == SHIFT_CLOSED) | (fn.IfNull(inv.needs_review, 0) == 1))
	)
	if pos_profile:
		cond &= inv.pos_profile.isin(pos_profile) if isinstance(pos_profile, (list, tuple)) else inv.pos_profile == pos_profile
	if overdue_only:
		cond &= inv.creation < add_to_date(now_datetime(), hours=-REVIEW_OVERDUE_HOURS)
	query = (search or "").strip().lstrip("#").strip()[:100]
	if query:
		pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
		cond &= inv.name.like(pattern) | inv.customer_name.like(pattern)
	return cond


def review_orders(pos_profile=None, search=None, overdue_only=False, limit=200, start=0, fields=None):
	"""Danh sách đơn cần xử lý, cũ nhất trước; mỗi dòng thêm age_minutes (từ lúc tạo đơn)."""
	from frappe.query_builder import DocType, Order
	from frappe.utils import cint, get_datetime

	inv = DocType("POS Invoice")
	base = ["name", "creation", "pos_profile", "custom_kitchen_status", "needs_review", "kitchen_outcome_reason",
		"consolidated_invoice", "status"]
	cols = list(dict.fromkeys([*(fields or []), *base]))
	rows = (
		frappe.qb.from_(inv)
		.select(*[inv[f] for f in cols])
		.where(_review_cond(inv, pos_profile, search, overdue_only))
		.orderby(inv.creation, order=Order.asc)
		.orderby(inv.name, order=Order.asc)
		.limit(min(max(cint(limit) or 200, 1), 500))
		.offset(max(cint(start), 0))
		.run(as_dict=True)
	)
	now = now_datetime()
	for r in rows:
		r["age_minutes"] = max(0, int((now - get_datetime(r.creation)).total_seconds() // 60))
		r["needs_review"] = cint(r.get("needs_review"))
	return rows


def review_counts(pos_profile=None):
	"""{review, overdue}: số đơn cần xử lý / quá REVIEW_OVERDUE_HOURS giờ (COUNT, cùng điều kiện với review_orders)."""
	from frappe.query_builder import DocType
	from frappe.query_builder.functions import Count

	inv = DocType("POS Invoice")

	def count(overdue):
		return frappe.utils.cint(
			frappe.qb.from_(inv).select(Count("*")).where(_review_cond(inv, pos_profile, overdue_only=overdue)).run()[0][0]
		)

	return {"review": count(False), "overdue": count(True)}


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


def remind_overdue_reviews(pos_profile=None):
	"""Job (cron mỗi giờ, hooks.scheduler_events): nhắc quản lý đơn cần xử lý quá REVIEW_OVERDUE_HOURS giờ.

	pos_profile: chỉ xét một POS Profile (script kiểm tra); job định kỳ để trống = mọi POS Profile.

	Idempotent: đơn đã có Notification Log (của chính đơn đó) trong REVIEW_REMIND_HOURS giờ qua -> bỏ qua. Không thêm field.
	"""
	from frappe.utils import add_to_date

	since = add_to_date(now_datetime(), hours=-REVIEW_REMIND_HOURS)
	sent = 0
	for r in review_orders(pos_profile=pos_profile, overdue_only=True, limit=500):
		if frappe.db.exists(
			"Notification Log",
			{"document_type": "POS Invoice", "document_name": r.name, "creation": [">=", since]},
		):
			continue
		hours = r.age_minutes // 60
		subject = _("{0} Đơn {1} ({2}) chờ xử lý {3} giờ.").format(
			REVIEW_REMIND_PREFIX, r.name, r.custom_kitchen_status or "", hours
		)
		try:
			if notify_profile_managers(r.pos_profile, subject, "POS Invoice", r.name):
				sent += 1
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title="MYPOS: lỗi nhắc đơn cần xử lý", message=f"{r.name}\n{frappe.get_traceback()}")
	return sent
