"""Khách vãng lai theo POS Profile (2026-11-24) — nguồn DUY NHẤT đọc `POS Profile.custom_walk_in_customer`.

Quy tắc:
- Mỗi POS Profile chọn một Customer làm khách vãng lai (người cấu hình tự tạo Customer). Không tự tạo, không
  rơi về tên Customer cố định nào. Nhiều profile được dùng chung một Customer.
- Đơn tại quầy không chọn khách -> Customer này; profile chưa cấu hình -> chặn tạo đơn (WALK_IN_MISSING_MSG).
- Khách vãng lai không tích / đổi điểm (Customer có Loyalty Program -> chặn lưu profile), không hiện ở tìm khách,
  không dùng được để đăng nhập web đặt món QR.
- Field chuẩn `POS Profile.customer` của ERPNext KHÔNG được đọc (app không dùng màn POS gốc).

Branch (2026-11-25): profile ĐANG BẬT phải có Branch (chặn lưu); chi nhánh đã có profile đang bật khác -> cảnh báo.

doc_events: POS Profile.validate -> `validate` (hooks.py).
"""

import frappe
from frappe import _

WALK_IN_FIELD = "custom_walk_in_customer"
WALK_IN_MISSING_MSG = "POS Profile chưa cấu hình Khách vãng lai. Vui lòng nhờ quản lý cấu hình."


def get_walk_in_customer(profile):
	"""Mã Customer khách vãng lai của POS Profile (doc hoặc tên); "" nếu chưa cấu hình."""
	if not profile:
		return ""
	if isinstance(profile, str):
		return frappe.db.get_value("POS Profile", profile, WALK_IN_FIELD) or ""
	return profile.get(WALK_IN_FIELD) or ""


def require_walk_in_customer(profile):
	"""Như get_walk_in_customer nhưng chưa cấu hình -> lỗi (dùng khi tạo đơn / xem trước giá tại quầy)."""
	customer = get_walk_in_customer(profile)
	if not customer:
		frappe.throw(_(WALK_IN_MISSING_MSG), title=_("Thiếu cấu hình"))
	return customer


def walk_in_by_profile(profile_names=None):
	"""{POS Profile: Customer khách vãng lai} trong 1 truy vấn (profile chưa cấu hình không có mặt).

	profile_names=None -> mọi POS Profile.
	"""
	filters = {WALK_IN_FIELD: ["is", "set"]}
	if profile_names is not None:
		names = sorted({p for p in profile_names if p})
		if not names:
			return {}
		filters["name"] = ["in", names]
	return dict(frappe.get_all("POS Profile", filters=filters, fields=["name", WALK_IN_FIELD], as_list=True))


def all_walk_in_customers():
	"""Tập Customer đang là khách vãng lai của BẤT KỲ POS Profile nào."""
	return set(walk_in_by_profile().values())


def mark_walk_in(rows, profile_key="pos_profile", customer_key="customer"):
	"""Gắn cờ `is_walk_in` cho từng dòng đơn (dict) theo POS Profile của chính đơn đó."""
	mapping = walk_in_by_profile([r.get(profile_key) for r in rows])
	for r in rows:
		walk_in = mapping.get(r.get(profile_key))
		r["is_walk_in"] = bool(walk_in) and r.get(customer_key) == walk_in
	return rows


def is_walk_in(pos_profile, customer):
	walk_in = get_walk_in_customer(pos_profile)
	return bool(walk_in) and customer == walk_in


# ---------------------------------------------------------------------------
# doc_events
# ---------------------------------------------------------------------------


def _check_walk_in(doc):
	customer = doc.get(WALK_IN_FIELD)
	if not customer:
		return
	row = frappe.db.get_value(
		"Customer", customer, ["name", "disabled", "loyalty_program", "mobile_number"], as_dict=True
	)
	if not row:
		frappe.throw(_("Khách vãng lai {0} không tồn tại. Tạo Customer trước rồi chọn lại.").format(customer))
	if row.disabled:
		frappe.throw(_("Khách vãng lai {0} đang bị vô hiệu hóa (disabled). Chọn Customer đang dùng.").format(customer))
	if row.loyalty_program:
		frappe.throw(
			_(
				"Khách vãng lai {0} đang gắn chương trình tích điểm {1}. Khách vãng lai không được tích điểm: "
				"bỏ Loyalty Program trên Customer hoặc chọn Customer khác."
			).format(customer, row.loyalty_program)
		)
	if row.get("mobile_number"):
		frappe.msgprint(
			_(
				"Khách vãng lai {0} đang có số điện thoại {1}. Nên để trống số điện thoại để không trùng khách thật."
			).format(customer, row.mobile_number),
			indicator="orange",
			alert=True,
		)


def _check_branch(doc):
	"""Profile đang bật phải gán Branch: /pos, màn khách, SePay, thẻ bàn, đơn QR đều tìm chi nhánh qua field này."""
	if doc.get("disabled"):
		return
	branch = doc.get("branch")
	if not branch:
		frappe.throw(
			_(
				"POS Profile {0} đang bật nhưng chưa gán Chi nhánh (Branch). "
				"Chọn Branch trước khi lưu, hoặc tắt profile (Disabled)."
			).format(doc.name or _("mới")),
			title=_("Thiếu chi nhánh"),
		)
	others = frappe.get_all(
		"POS Profile",
		filters={"branch": branch, "disabled": 0, "name": ["!=", doc.name or ""]},
		pluck="name",
		order_by="name asc",
	)
	if others:
		frappe.msgprint(
			_(
				"Chi nhánh {0} đã có POS Profile đang bật: {1}. Đơn QR của chi nhánh sẽ ưu tiên profile đang mở ca, "
				"sau đó theo tên (A→Z). Nên giữ mỗi chi nhánh một POS Profile đang bật."
			).format(branch, ", ".join(others)),
			indicator="orange",
			alert=True,
		)


def validate(doc, method=None):
	_check_branch(doc)
	_check_walk_in(doc)
