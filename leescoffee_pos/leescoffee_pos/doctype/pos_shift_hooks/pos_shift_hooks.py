"""Quy tắc mở / đóng ca POS (POS Opening Entry, POS Closing Entry) — doc_events trong hooks.py.

Quy tắc (2026-11-20):
- Mỗi POS Profile = 1 chi nhánh; "Applicable for Users" của profile = thu ngân của chi nhánh.
- Mở ca: Cashier (`user`) phải là chính người đang thao tác và thuộc Applicable for Users của profile.
- Đóng ca: chỉ đóng được ca có Cashier là chính mình.
- POS MANAGER / System Manager / Administrator (`pos_api._pos_roles` -> manager) được mở/đóng thay người khác
  (Cashier vẫn phải thuộc Applicable for Users); ghi comment người thao tác thay.
- POS KITCHEN và role khác: không mở/đóng ca.
- ERPNext chỉ cho 1 ca Open mỗi POS Profile (giữ nguyên); báo rõ "Ca của {tên} chưa đóng".

Kiểm tra ở `before_validate` (chạy TRƯỚC validate của ERPNext để thông báo tiếng Việt hiện trước) và lặp lại ở
`before_submit` (người submit có thể khác người tạo). Không đụng logic đơn POS Invoice.
"""

import frappe
from frappe import _


def _actor_roles():
	from leescoffee_pos.leescoffee_pos.api.pos_api import _pos_roles

	return _pos_roles(frappe.session.user)


def _require_shift_role(roles):
	if not (roles["manager"] or roles["cashier"]):
		frappe.throw(
			_("Tài khoản không có quyền mở/đóng ca (cần POS CASHIER hoặc POS MANAGER)."),
			frappe.PermissionError,
		)


def _user_label(user):
	name = frappe.db.get_value("User", user, "full_name") if user else None
	return f"{name} ({user})" if name and name != user else (user or "?")


def _check_applicable(pos_profile, user):
	"""Cashier phải nằm trong Applicable for Users của POS Profile (danh sách rỗng cũng chặn)."""
	if not frappe.db.exists(
		"POS Profile User",
		{"parent": pos_profile, "parenttype": "POS Profile", "parentfield": "applicable_for_users", "user": user},
	):
		frappe.throw(
			_(
				"{0} không thuộc Applicable for Users của POS Profile {1}. "
				"Quản lý cần thêm thu ngân này vào POS Profile trước khi mở ca."
			).format(_user_label(user), pos_profile),
			frappe.PermissionError,
		)


# ---------------------------------------------------------------------------
# POS Opening Entry
# ---------------------------------------------------------------------------


def _check_opening(doc):
	roles = _actor_roles()
	_require_shift_role(roles)
	actor = frappe.session.user

	if not doc.user:
		frappe.throw(_("Chưa chọn Cashier cho ca."))
	if not roles["manager"] and doc.user != actor:
		frappe.throw(
			_("Bạn chỉ được mở ca cho chính mình (Cashier phải là {0}).").format(_user_label(actor)),
			frappe.PermissionError,
		)
	if not doc.pos_profile:
		frappe.throw(_("Chưa chọn POS Profile cho ca."))
	_check_applicable(doc.pos_profile, doc.user)

	# Ca Open khác của cùng profile (ERPNext cũng chặn, nhưng thông báo tiếng Anh và không nêu tên người).
	other = frappe.get_all(
		"POS Opening Entry",
		filters={
			"pos_profile": doc.pos_profile,
			"status": "Open",
			"docstatus": 1,
			"name": ["!=", doc.name or ""],
		},
		fields=["name", "user"],
		limit=1,
	)
	if other:
		frappe.throw(
			_("Ca của {0} tại {1} chưa đóng ({2}). Đóng ca đó trước khi mở ca mới.").format(
				_user_label(other[0].user), doc.pos_profile, other[0].name
			),
			title=_("Ca chưa đóng"),
		)


def opening_before_validate(doc, method=None):
	_check_opening(doc)


def opening_before_submit(doc, method=None):
	_check_opening(doc)


def opening_on_submit(doc, method=None):
	actor = frappe.session.user
	if doc.user != actor:
		doc.add_comment("Info", _("Mở ca thay cho {0} bởi {1}.").format(_user_label(doc.user), _user_label(actor)))


# ---------------------------------------------------------------------------
# POS Closing Entry
# ---------------------------------------------------------------------------


def _check_closing(doc):
	roles = _actor_roles()
	_require_shift_role(roles)
	actor = frappe.session.user

	if not doc.pos_opening_entry:
		frappe.throw(_("Chưa chọn ca (POS Opening Entry) cần đóng."))
	shift_user = frappe.db.get_value("POS Opening Entry", doc.pos_opening_entry, "user")
	if not shift_user:
		frappe.throw(_("Không tìm thấy ca {0}.").format(doc.pos_opening_entry))
	# ERPNext gom đơn theo owner == closing.user: Cashier của phiếu đóng ca phải là Cashier của ca, kể cả khi đóng thay.
	if doc.user != shift_user:
		frappe.throw(
			_("Cashier của phiếu đóng ca phải là Cashier của ca {0} ({1}).").format(
				doc.pos_opening_entry, _user_label(shift_user)
			)
		)
	if not roles["manager"] and shift_user != actor:
		frappe.throw(
			_("Bạn chỉ được đóng ca của chính mình (ca {0} của {1}).").format(
				doc.pos_opening_entry, _user_label(shift_user)
			),
			frappe.PermissionError,
		)

	# Còn đơn Draft (QR chỉ tính đơn còn hạn thanh toán) -> chặn. Đơn đã thanh toán (kể cả pha chế chưa xong) không chặn.
	# Quản lý: pos_api.force_close_shift hủy hết Draft (có lý do + log) rồi mới tạo phiếu đóng ca.
	from leescoffee_pos.leescoffee_pos.doctype.mypos_order_cancel_log.order_cancel import (
		closing_block_message,
		closing_blockers,
	)

	blockers = closing_blockers(doc.pos_profile)
	if blockers:
		frappe.throw(closing_block_message(blockers), title=_("Còn đơn chưa thanh toán"))


def closing_before_validate(doc, method=None):
	_check_closing(doc)


def closing_before_submit(doc, method=None):
	_check_closing(doc)


def closing_on_submit(doc, method=None):
	actor = frappe.session.user
	if doc.user == actor:
		return
	text = _("Đóng ca thay cho {0} bởi {1}.").format(_user_label(doc.user), _user_label(actor))
	doc.add_comment("Info", text)
	opening = frappe.get_doc("POS Opening Entry", doc.pos_opening_entry)
	opening.add_comment("Info", text + f" ({doc.name})")
