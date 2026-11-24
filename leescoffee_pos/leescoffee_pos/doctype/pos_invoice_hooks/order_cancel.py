"""Hủy đơn Draft — MỘT nơi cho mọi đường hủy và mốc thời gian (2026-11-23).

Dùng bởi: pos_api.cancel_draft_order (hủy tay ở Orders / nút "Hủy đơn" trên Desk), kitchen_status.shift_open_orders
(chặn đóng ca khi còn Draft), customer_order_api (hạn QR), job `auto_cancel_stale_drafts` (hooks.scheduler_events).

Quy tắc (Van chốt 2026-11-20, đổi cách hủy 2026-11-23):
- Hủy = đơn CHUYỂN Cancelled (docstatus 2, status "Cancelled"), KHÔNG xóa; lý do lưu ở `POS Invoice.custom_cancel_reason`
  với tiền tố nguồn ("Thủ công: …", "Tự động (QR hết hạn): …", "Tự động (quá 2 giờ): …") + Comment trên đơn.
- Draft QR: khách trả trong QR_PAY_WINDOW_MINUTES; webhook còn khớp thêm QR_CLEANUP_GRACE_MINUTES; sau đó job tự hủy.
  QR còn trong hạn chặn đóng ca, quá hạn thì không.
- Draft kênh khác QR: chặn đóng ca khi còn tồn; job tự hủy sau POS_DRAFT_AUTO_CANCEL_MINUTES.
- Frappe không cho save() đổi docstatus 0 -> 2 nên ghi bằng frappe.db.set_value (cả bảng con). Hook on_cancel không chạy:
  Draft chưa có GL / tồn kho / điểm, thẻ bàn chưa đổi trạng thái (chỉ on_submit đổi) — "đang giữ" chỉ tính docstatus 0/1.
"""

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, get_datetime, now_datetime

# --- Mốc thời gian: chỉ khai ở đây ---------------------------------------------------------------
QR_PAY_WINDOW_MINUTES = 15  # khách QR thấy / sinh QR thanh toán trong khoảng này
QR_CLEANUP_GRACE_MINUTES = 5  # đệm cho webhook chuyển khoản trễ trước khi job hủy đơn QR
POS_DRAFT_AUTO_CANCEL_MINUTES = 120  # Draft kênh khác QR tự hủy sau khoảng này

CHANNEL_QR = "QR"

SOURCE_MANUAL = "Thủ công"
SOURCE_AUTO_QR = "Tự động (QR hết hạn)"


def source_auto_pos():
	"""Nguồn tự hủy Draft kênh khác QR, theo POS_DRAFT_AUTO_CANCEL_MINUTES ("Tự động (quá 2 giờ)")."""
	m = POS_DRAFT_AUTO_CANCEL_MINUTES
	return _("Tự động (quá {0} giờ)").format(m // 60) if m % 60 == 0 else _("Tự động (quá {0} phút)").format(m)


REASON_OTHER = "Khác"
MANUAL_REASONS = ("Khách đổi ý", "Đặt nhầm", "Khách không lấy", REASON_OTHER)
REASON_LEGACY = "Không ghi lý do (giao diện cũ)"
REASON_QR_EXPIRED = "QR hết hạn không thanh toán"

CLOSING_LIST_LIMIT = 10  # số mã đơn liệt kê trong thông báo chặn đóng ca


def reason_pos_stale():
	"""Lý do tự hủy Draft kênh khác QR ("Tự hủy quá 2 giờ")."""
	m = POS_DRAFT_AUTO_CANCEL_MINUTES
	return _("Tự hủy quá {0} giờ").format(m // 60) if m % 60 == 0 else _("Tự hủy quá {0} phút").format(m)


def cancel_text(source, reason, note=None):
	"""Chuỗi lưu vào custom_cancel_reason: "<nguồn>: <lý do>[ — <ghi chú>]"."""
	note = (note or "").strip()
	return f"{source}: {reason}" + (f" — {note}" if note else "")


# --- Hủy ------------------------------------------------------------------------------------------


def cancel_draft(invoice_name, reason, source, note=None):
	"""Chuyển đơn Draft sang Cancelled + lưu lý do + Comment. Chạy trong giao dịch của người gọi (không commit).

	Khóa dòng (FOR UPDATE) rồi kiểm lại docstatus: webhook / thu ngân có thể vừa thanh toán. set_value đổi `modified`
	nên save/submit song song trên bản cũ bị Frappe từ chối (TimestampMismatchError).
	Trả {invoice_name, buzzer, cancel_reason}.
	"""
	row = frappe.db.sql(
		"SELECT `name`, `docstatus`, `is_return`, `buzzer`, `owner` FROM `tabPOS Invoice` WHERE `name` = %s FOR UPDATE",
		(invoice_name,),
		as_dict=True,
	)
	if not row:
		frappe.throw(_("Không tìm thấy đơn {0}.").format(invoice_name), frappe.DoesNotExistError)
	row = row[0]
	if cint(row.docstatus) != 0:
		frappe.throw(_("Đơn {0} đã thanh toán hoặc đã hủy, không hủy được.").format(invoice_name))
	if cint(row.is_return):
		frappe.throw(_("Đơn {0} là đơn trả hàng, không hủy theo cách này.").format(invoice_name))

	text = cancel_text(source, reason, note)
	frappe.db.set_value(
		"POS Invoice",
		invoice_name,
		{"docstatus": 2, "status": "Cancelled", "custom_cancel_reason": text},
		update_modified=True,
	)
	# Bảng con theo đơn (như hủy thật): truy vấn lọc docstatus dòng con (vd. tồn giữ chỗ POS) không tính nhầm.
	for df in frappe.get_meta("POS Invoice").get_table_fields():
		frappe.db.sql(
			f"UPDATE `tab{df.options}` SET `docstatus` = 2 WHERE `parent` = %s AND `parenttype` = 'POS Invoice'",
			(invoice_name,),
		)
	frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": "POS Invoice",
			"reference_name": invoice_name,
			"content": _("Hủy đơn: {0}. Bởi {1}.").format(text, frappe.session.user),
		}
	).insert(ignore_permissions=True)
	# Màn khách đang hiện đơn này -> về màn chờ (sau commit, lỗi không chặn hủy).
	from leescoffee_pos.leescoffee_pos.api.customer_display_api import touch_cancelled

	touch_cancelled(invoice_name, row.owner)
	return {"invoice_name": invoice_name, "buzzer": row.buzzer, "cancel_reason": text}


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
	return _("Còn {0} đơn chưa thanh toán: {1}{2}. Thu tiền hoặc hủy ở màn Đơn hàng trước khi đóng ca.").format(
		len(names), shown, extra
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


def _cancel_batch(names, reason, source):
	done = 0
	for name in names:
		try:
			# Đọc lại ngay trước khi hủy (webhook / thu ngân có thể vừa thanh toán); cancel_draft kiểm lại dưới khóa dòng.
			if frappe.db.get_value("POS Invoice", name, "docstatus") != 0:
				continue
			cancel_draft(name, reason, source)
			frappe.db.commit()
			done += 1
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title="MYPOS: lỗi tự hủy đơn Draft", message=f"{name}\n{frappe.get_traceback()}")
	return done


def auto_cancel_qr_drafts(older_than_minutes=None):
	"""Hủy đơn QR Draft quá QR_PAY_WINDOW_MINUTES + QR_CLEANUP_GRACE_MINUTES. Idempotent."""
	minutes = QR_PAY_WINDOW_MINUTES + QR_CLEANUP_GRACE_MINUTES if older_than_minutes is None else older_than_minutes
	return _cancel_batch(_stale_drafts(True, minutes), REASON_QR_EXPIRED, SOURCE_AUTO_QR)


def auto_cancel_pos_drafts(older_than_minutes=None):
	"""Hủy đơn Draft kênh khác QR quá POS_DRAFT_AUTO_CANCEL_MINUTES. Idempotent."""
	minutes = POS_DRAFT_AUTO_CANCEL_MINUTES if older_than_minutes is None else older_than_minutes
	return _cancel_batch(_stale_drafts(False, minutes), reason_pos_stale(), source_auto_pos())


def auto_cancel_stale_drafts():
	"""Job (cron 5 phút, hooks.scheduler_events). Không đụng đơn đã submit, đơn trả hàng."""
	return {"qr": auto_cancel_qr_drafts(), "pos": auto_cancel_pos_drafts()}
