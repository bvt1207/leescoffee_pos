"""Hủy đơn Draft + nhật ký (MYPOS Order Cancel Log) — MỘT nơi cho mọi đường hủy và mốc thời gian.

Dùng bởi: pos_api.cancel_draft_order (hủy tay ở Orders), pos_api.force_close_shift (đóng ca bắt buộc),
pos_shift_hooks (chặn đóng ca khi còn Draft), customer_order_api (hạn QR), sepay.sepay_webhook (tiền đến sau khi đơn đã hủy),
job `auto_cancel_stale_drafts` (hooks.scheduler_events).

Quy tắc (Van chốt 2026-11-20):
- Draft QR: khách trả trong QR_PAY_WINDOW_MINUTES; webhook còn khớp thêm QR_CLEANUP_GRACE_MINUTES; sau đó job tự hủy
  ("QR hết hạn không thanh toán"). QR còn trong hạn chặn đóng ca, quá hạn thì không.
- Draft kênh khác QR: chặn đóng ca khi còn tồn; job tự hủy sau POS_DRAFT_AUTO_CANCEL_MINUTES.
- Đơn POS Invoice bị xóa khi hủy (Comment bị xóa theo) -> log nằm ở DocType riêng.
"""

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, flt, get_datetime, now_datetime

# --- Mốc thời gian: chỉ khai ở đây ---------------------------------------------------------------
QR_PAY_WINDOW_MINUTES = 15  # khách QR thấy / sinh QR thanh toán trong khoảng này
QR_CLEANUP_GRACE_MINUTES = 5  # đệm cho webhook chuyển khoản trễ trước khi job hủy đơn QR
POS_DRAFT_AUTO_CANCEL_MINUTES = 120  # Draft kênh khác QR tự hủy sau khoảng này

CHANNEL_QR = "QR"
LOG_DOCTYPE = "MYPOS Order Cancel Log"

SOURCE_MANUAL = "Thủ công"
SOURCE_AUTO = "Tự động"
SOURCE_CLOSE = "Đóng ca"

REASON_OTHER = "Khác"
MANUAL_REASONS = ("Khách đổi ý", "Đặt nhầm", "Khách không lấy", REASON_OTHER)
REASON_LEGACY = "Không ghi lý do (giao diện cũ)"
REASON_CLOSE = "Hủy khi đóng ca"
REASON_QR_EXPIRED = "QR hết hạn không thanh toán"

CLOSING_LIST_LIMIT = 10  # số mã đơn liệt kê trong thông báo chặn đóng ca
_CODE_STRIP_CHARS = ("-", ".", "/", "_", " ")  # giống sepay._find_invoice_by_code
_ORPHAN_LOOKUP_DAYS = 30


def reason_pos_stale():
	"""Lý do tự hủy Draft kênh khác QR, theo POS_DRAFT_AUTO_CANCEL_MINUTES ("Tự hủy quá 2 giờ")."""
	m = POS_DRAFT_AUTO_CANCEL_MINUTES
	return _("Tự hủy quá {0} giờ").format(m // 60) if m % 60 == 0 else _("Tự hủy quá {0} phút").format(m)


def _open_shift_name(pos_profile):
	if not pos_profile:
		return None
	return frappe.db.get_value(
		"POS Opening Entry", {"pos_profile": pos_profile, "status": "Open", "docstatus": 1}, "name"
	)


# --- Hủy + log ------------------------------------------------------------------------------------


def cancel_draft_with_log(invoice_name, reason, source, note=None):
	"""Ghi MYPOS Order Cancel Log rồi xóa đơn Draft. Chạy trong giao dịch của người gọi (không commit).

	Thẻ rung tự nhả: "đang giữ" chỉ tính trên đơn còn tồn (pos_api._assign_buzzer / get_buzzers).
	Trả {invoice_name, log, buzzer}.
	"""
	invoice = frappe.get_doc("POS Invoice", invoice_name)
	if invoice.docstatus != 0:
		frappe.throw(_("Đơn {0} đã thanh toán hoặc đã hủy, không hủy được.").format(invoice_name))
	if cint(invoice.get("is_return")):
		frappe.throw(_("Đơn {0} là đơn trả hàng, không hủy theo cách này.").format(invoice_name))

	items = "; ".join(f"{row.item_name or row.item_code} x{flt(row.qty):g}" for row in invoice.items)
	log = frappe.get_doc(
		{
			"doctype": LOG_DOCTYPE,
			"invoice_name": invoice.name,
			"invoice_creation": invoice.creation,
			"cancelled_at": now_datetime(),
			"source": source,
			"reason": reason,
			"note": (note or "").strip() or None,
			"cancelled_by": frappe.session.user,
			"pos_profile": invoice.pos_profile,
			"branch": frappe.db.get_value("POS Profile", invoice.pos_profile, "branch") if invoice.pos_profile else None,
			"pos_opening_entry": _open_shift_name(invoice.pos_profile),
			"customer": invoice.customer,
			"customer_name": invoice.customer_name,
			"order_type": invoice.get("order_type"),
			"order_channel": invoice.get("order_channel"),
			"grand_total": flt(invoice.get("rounded_total") or invoice.grand_total),
			"currency": invoice.currency,
			"buzzer": invoice.get("buzzer"),
			"payment_code": invoice.get("payment_code"),
			"payment_status": invoice.get("payment_status"),
			"items_summary": items[:2000],
		}
	)
	log.insert(ignore_permissions=True)
	buzzer = invoice.get("buzzer")
	frappe.delete_doc("POS Invoice", invoice.name, ignore_permissions=True)
	return {"invoice_name": invoice_name, "log": log.name, "buzzer": buzzer}


# --- Đóng ca --------------------------------------------------------------------------------------


def closing_blockers(pos_profile):
	"""Mã đơn Draft (không phải trả hàng) làm chặn đóng ca: kênh khác QR -> mọi đơn; QR -> còn trong hạn thanh toán."""
	if not pos_profile:
		return []
	since_qr = add_to_date(now_datetime(), minutes=-QR_PAY_WINDOW_MINUTES)
	rows = frappe.get_all(
		"POS Invoice",
		filters={"pos_profile": pos_profile, "docstatus": 0, "is_return": 0},
		fields=["name", "order_channel", "creation"],
		order_by="creation asc",
		limit=1000,
	)
	return [r.name for r in rows if r.order_channel != CHANNEL_QR or get_datetime(r.creation) >= since_qr]


def closing_block_message(names):
	shown = ", ".join(names[:CLOSING_LIST_LIMIT])
	more = len(names) - CLOSING_LIST_LIMIT
	extra = _(" và {0} đơn khác").format(more) if more > 0 else ""
	return _(
		"Còn {0} đơn chưa thanh toán: {1}{2}. Thu tiền hoặc hủy ở màn Đơn hàng trước khi đóng ca "
		"(quản lý có thể dùng Đóng ca bắt buộc)."
	).format(len(names), shown, extra)


def all_drafts(pos_profile):
	"""Mọi đơn Draft (không phải trả hàng) của POS Profile — đóng ca bắt buộc hủy hết."""
	return frappe.get_all(
		"POS Invoice",
		filters={"pos_profile": pos_profile, "docstatus": 0, "is_return": 0},
		order_by="creation asc",
		pluck="name",
	)


# --- Job tự hủy -----------------------------------------------------------------------------------


def _stale_drafts(qr, older_than_minutes):
	cutoff = add_to_date(now_datetime(), minutes=-cint(older_than_minutes))
	channel_cond = "IFNULL(`order_channel`, '') = %(qr)s" if qr else "IFNULL(`order_channel`, '') != %(qr)s"
	return frappe.db.sql(
		f"""
		SELECT `name` FROM `tabPOS Invoice`
		WHERE `docstatus` = 0 AND IFNULL(`is_return`, 0) = 0 AND {channel_cond}
		  AND `creation` < %(cutoff)s AND IFNULL(`payment_status`, '') != 'Đã thanh toán'
		ORDER BY `creation` ASC
		LIMIT 500
		""",
		{"qr": CHANNEL_QR, "cutoff": cutoff},
		pluck=True,
	)


def _cancel_batch(names, reason):
	done = 0
	for name in names:
		try:
			# Đọc lại ngay trước khi hủy (webhook / thu ngân có thể vừa thanh toán).
			if frappe.db.get_value("POS Invoice", name, "docstatus") != 0:
				continue
			cancel_draft_with_log(name, reason, SOURCE_AUTO)
			frappe.db.commit()
			done += 1
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title="MYPOS: lỗi tự hủy đơn Draft", message=f"{name}\n{frappe.get_traceback()}")
	return done


def auto_cancel_qr_drafts(older_than_minutes=None):
	"""Hủy + log đơn QR Draft quá QR_PAY_WINDOW_MINUTES + QR_CLEANUP_GRACE_MINUTES. Idempotent."""
	minutes = QR_PAY_WINDOW_MINUTES + QR_CLEANUP_GRACE_MINUTES if older_than_minutes is None else older_than_minutes
	return _cancel_batch(_stale_drafts(True, minutes), REASON_QR_EXPIRED)


def auto_cancel_pos_drafts(older_than_minutes=None):
	"""Hủy + log đơn Draft kênh khác QR quá POS_DRAFT_AUTO_CANCEL_MINUTES. Idempotent."""
	minutes = POS_DRAFT_AUTO_CANCEL_MINUTES if older_than_minutes is None else older_than_minutes
	return _cancel_batch(_stale_drafts(False, minutes), reason_pos_stale())


def auto_cancel_stale_drafts():
	"""Job (cron 5 phút, hooks.scheduler_events). Không đụng đơn đã submit, đơn trả hàng."""
	return {"qr": auto_cancel_qr_drafts(), "pos": auto_cancel_pos_drafts()}


# --- Tiền đến sau khi đơn đã hủy (webhook SePay) -------------------------------------------------


def _find_log_by_code(content, normalized_content):
	if not normalized_content:
		return None
	exact = frappe.get_all(
		LOG_DOCTYPE, filters={"payment_code": (content or "").strip()}, order_by="creation desc", limit=1, pluck="name"
	)
	if exact:
		return exact[0]
	expr = "UPPER(`payment_code`)"
	for ch in _CODE_STRIP_CHARS:
		expr = f"REPLACE({expr}, '{ch}', '')"
	since = add_to_date(now_datetime(), days=-_ORPHAN_LOOKUP_DAYS)
	rows = frappe.db.sql(
		f"""SELECT `name` FROM `tab{LOG_DOCTYPE}`
		WHERE `creation` >= %(since)s AND IFNULL(`payment_code`, '') != '' AND {expr} = %(code)s
		ORDER BY `creation` DESC LIMIT 2""",
		{"since": since, "code": normalized_content},
		pluck=True,
	)
	return rows[0] if len(rows) == 1 else None



def record_orphan_payment(content, normalized_content, payload, transaction_id, amount, verify_branch_key):
	"""Webhook không thấy đơn: nếu mã thanh toán thuộc đơn ĐÃ HỦY -> ghi giao dịch mồ côi vào log, cảnh báo MANAGER.

	`verify_branch_key(branch) -> bool` kiểm API key SePay theo Branch của log (sai -> PermissionError như webhook thường).
	Idempotent theo transaction_id. Trả dict phản hồi cho SePay, hoặc None nếu mã không thuộc log nào (hành vi cũ).
	"""
	import json

	log_name = _find_log_by_code(content, normalized_content)
	if not log_name:
		return None
	log = frappe.db.get_value(
		LOG_DOCTYPE,
		log_name,
		["name", "branch", "pos_profile", "invoice_name", "orphan_transaction_ref", "orphan_payload"],
		as_dict=True,
	)
	if not verify_branch_key(log.branch):
		frappe.log_error(title="SePay webhook: sai hoặc thiếu API key", message=f"cancel_log={log.name}\nbranch={log.branch}")
		raise frappe.PermissionError(_("Webhook SePay không hợp lệ."))

	message = _("Đơn {0} đã hủy trước khi nhận tiền; giao dịch cần đối soát.").format(log.invoice_name)
	if transaction_id and transaction_id in (log.orphan_transaction_ref or "").split(","):
		return {"success": True, "needs_review": True, "message": message}

	refs = ",".join(filter(None, [log.orphan_transaction_ref, transaction_id]))
	entry = json.dumps(payload, ensure_ascii=False, default=str)[:4000]
	old_payload = log.orphan_payload or ""
	frappe.db.set_value(
		LOG_DOCTYPE,
		log.name,
		{
			"needs_review": 1,
			"orphan_transaction_ref": refs,
			"orphan_amount": flt(amount),
			"orphan_received_at": now_datetime(),
			"orphan_payload": (old_payload + "\n" if old_payload else "") + entry,
		},
	)
	frappe.log_error(
		title="SePay: giao dịch mồ côi (đơn đã hủy)",
		message=f"cancel_log={log.name}\ninvoice={log.invoice_name}\ntransaction={transaction_id}\namount={amount}",
	)
	# Quản lý của chi nhánh (kitchen_status.notify_profile_managers); không có ai -> mọi POS MANAGER (tiền đến không được mất cảnh báo).
	from ..pos_invoice_hooks.kitchen_status import notify_profile_managers

	notify_profile_managers(
		log.pos_profile,
		_("Tiền chuyển khoản {0} đến sau khi đơn {1} đã hủy — cần đối soát.").format(
			frappe.format_value(flt(amount), {"fieldtype": "Currency"}), log.invoice_name
		),
		LOG_DOCTYPE,
		log.name,
		fallback_all=True,
	)
	return {"success": True, "needs_review": True, "message": message}
