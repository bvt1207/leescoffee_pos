"""Màn theo dõi đơn cho khách nhìn (/pos/status, treo TV ở quầy) — CHỈ ĐỌC (2026-11-27).

    POST /api/method/mypos.mypos.api.order_status_api.<tên_hàm>

- Cột "Đang chuẩn bị" = đơn Chưa làm, "Sẵn sàng nhận món" = đơn Đã làm. Cùng điều kiện đơn với màn Pha chế
  (`pos_api.get_kitchen_orders`): docstatus 1, status "Paid", đúng POS Profile. Đơn Đã hoàn thành / Khách không nhận /
  Không thực hiện được / Cancelled / Draft / trả hàng / Consolidated không hiện.
- POS Profile: Cashier / Kitchen = profile user thuộc về (`require_membership=True`, cùng lỗi với màn Pha chế);
  quản lý (POS MANAGER / System Manager / Administrator) được chọn profile đang bật.
- Dữ liệu trả TỐI THIỂU, rút gọn ở server: mã ngắn, tên gọi (từ cuối của tên, ≤ NAME_MAX ký tự), nhãn loại đơn / thẻ bàn,
  thời điểm, món (CHỈ tên món + số lượng, 2026-11-27). Không trả tên hóa đơn đầy đủ, mã / tên đầy đủ / SĐT khách, tiền, giá,
  tùy chọn món, ghi chú.
- Cập nhật: dùng chung phiên bản thay đổi theo POS Profile (`change_feed`, `docs/rules/realtime.md`).
Chi tiết: `docs/rules/order_status.md`.
"""

import re

import frappe
from frappe import _

from ..doctype.branch_config.branch_config import get_brand_info, resolve_pos_profile_name
from ..doctype.pos_invoice_hooks.change_feed import PROFILE_CACHE_PREFIX, PROFILE_CACHE_SECONDS, get_version
from ..doctype.pos_profile_hooks.pos_profile_hooks import walk_in_by_profile
from .pos_api import _pos_roles, _require_pos_role, _set_buzzer_numbers

PREPARING = "Chưa làm"
READY = "Đã làm"
# Số đơn tối đa trả chi tiết mỗi cột (phần vượt chỉ trả số đếm). TV 1080p chứa tối đa ~20 dòng / cột.
MAX_ROWS = 60
# Độ dài tối đa của tên gọi hiển thị (ký tự).
NAME_MAX = 12
# Số món tối đa trả cho mỗi đơn (sau khi gộp cùng tên); phần vượt chỉ trả số đếm `items_more`.
ITEM_LIMIT = 12
# Từ cuối có từ chừng này chữ số trở lên -> coi như số điện thoại / mã, không hiện.
NAME_DIGIT_LIMIT = 4
# Cache POS Profile cho request poll phiên bản. Dùng chung tiền tố change_feed.PROFILE_CACHE_PREFIX nên lưu / xóa POS Profile
# (clear_profile_cache) xóa luôn khóa này; tách nhánh "status:" để không lẫn với cache của get_pos_changes (khác điều kiện).
STATUS_CACHE_PREFIX = PROFILE_CACHE_PREFIX + "status:"

_DIGITS_AT_END = re.compile(r"(\d+)$")


# ---------------------------------------------------------------------------
# Rút gọn (thuần, kiểm được độc lập)
# ---------------------------------------------------------------------------


def short_order_code(invoice_name):
	"""Mã gọi khách: cùng quy tắc `shortOrderNo` (pos/src/lib/format.ts) của tem ly / màn Pha chế / toast thu ngân.

	"ACC-PSINV-2026-00088" -> "#00088"; không có cụm số cuối -> giữ nguyên.
	"""
	name = str(invoice_name or "")
	match = _DIGITS_AT_END.search(name)
	return f"#{match.group(1)}" if match else name


def short_call_name(full_name):
	"""Tên gọi hiện trên TV: CHỈ từ cuối của tên, tối đa NAME_MAX ký tự (cắt + "…").

	Trả "" khi tên trống hoặc từ cuối chứa >= NAME_DIGIT_LIMIT chữ số (tránh lộ SĐT khi khách đặt tên bằng số).
	Giữ nguyên dấu tiếng Việt. "Nguyễn Văn Thạch" -> "Thạch".
	"""
	words = str(full_name or "").split()
	if not words:
		return ""
	last = words[-1].strip(".,;:!?-_()[]{}\"'")
	if not last or sum(ch.isdigit() for ch in last) >= NAME_DIGIT_LIMIT:
		return ""
	return last if len(last) <= NAME_MAX else last[: NAME_MAX - 1] + "…"


def _qty(value):
	"""Số lượng hiển thị: 2.0 -> 2 (int), 1.5 giữ nguyên."""
	value = float(value or 0)
	return int(value) if value.is_integer() else value


def items_by_invoice(names):
	"""{tên hóa đơn: ([{name, qty}], số món bị bỏ)} trong MỘT truy vấn. CHỈ tên món + số lượng (không giá, tùy chọn, ghi chú).

	Gộp các dòng cùng tên món (cùng món khác tùy chọn -> cộng số lượng), giữ thứ tự dòng đầu tiên; tối đa ITEM_LIMIT món mỗi đơn.
	"""
	if not names:
		return {}
	rows = frappe.get_all(
		"POS Invoice Item",
		filters={"parent": ["in", list(names)], "parenttype": "POS Invoice"},
		fields=["parent", "item_name", "qty"],
		order_by="parent asc, idx asc",
	)
	merged = {}
	for r in rows:
		lines = merged.setdefault(r.parent, {})
		key = (r.item_name or "").strip()
		if not key:
			continue
		lines[key] = lines.get(key, 0) + float(r.qty or 0)
	out = {}
	for parent, lines in merged.items():
		items = [{"name": name, "qty": _qty(qty)} for name, qty in lines.items()]
		out[parent] = (items[:ITEM_LIMIT], max(0, len(items) - ITEM_LIMIT))
	return out


def order_label(order_type, buzzer_number):
	"""Nhãn loại đơn: thẻ bàn (Dine In có thẻ) > Tại quán > Mang đi."""
	if order_type == "Dine In":
		return _("Thẻ bàn {0}").format(buzzer_number) if buzzer_number else _("Tại quán")
	return _("Mang đi")


# ---------------------------------------------------------------------------
# POS Profile + quyền
# ---------------------------------------------------------------------------


def _enabled_profiles():
	return [p.name for p in frappe.get_all("POS Profile", filters={"disabled": 0}, fields=["name"], order_by="name asc")]


def _resolve_profile(pos_profile=None, cached=False):
	"""(profile, roles). Không phải quản lý -> bỏ qua `pos_profile`, profile user thuộc về (cùng lỗi màn Pha chế).

	cached=True (poll phiên bản): nhớ kết quả STATUS_CACHE_PREFIX + user (+ profile đã chọn) PROFILE_CACHE_SECONDS giây.
	"""
	roles = _pos_roles()
	_require_pos_role(roles)
	chosen = (pos_profile or "").strip() if roles["manager"] else ""
	key = f"{STATUS_CACHE_PREFIX}{frappe.session.user}:{chosen}"
	if cached:
		name = frappe.cache.get_value(key)
		if name:
			return name, roles

	if chosen:
		if not frappe.db.exists("POS Profile", {"name": chosen, "disabled": 0}):
			frappe.throw(_("POS Profile {0} không tồn tại hoặc đã tắt.").format(chosen), title=_("Chọn POS Profile"))
		name = chosen
	else:
		name = resolve_pos_profile_name(require_membership=not roles["manager"])

	if cached:
		frappe.cache.set_value(key, name, expires_in_sec=PROFILE_CACHE_SECONDS)
	return name, roles


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_order_status_config(pos_profile=None):
	"""Thương hiệu (Branch của profile) + danh sách profile để quản lý chọn. Gọi lúc mở màn (và định kỳ, thưa)."""
	profile, roles = _resolve_profile(pos_profile)
	branch = frappe.db.get_value("POS Profile", profile, "branch")
	brand = get_brand_info(branch) if branch else {}
	return {
		"profile": profile,
		"profiles": _enabled_profiles() if roles["manager"] else [],
		"brand": {"name": brand.get("name") or "", "logo": brand.get("logo") or ""},
	}


@frappe.whitelist()
def get_order_status_changes(pos_profile=None):
	"""Phiên bản thay đổi của profile đang hiện — chỉ đọc Redis (+ cache profile). Màn poll hàm này."""
	profile, _roles = _resolve_profile(pos_profile, cached=True)
	return {"profile": profile, "v": get_version(profile)}


@frappe.whitelist()
def get_order_status_board(pos_profile=None):
	"""Hai cột của màn theo dõi đơn. Mỗi dòng {code, name, label, at, items: [{name, qty}], items_more}; `more` = số đơn vượt MAX_ROWS (không trả chi tiết)."""
	profile, _roles = _resolve_profile(pos_profile)
	# Đọc phiên bản TRƯỚC khi truy vấn: thay đổi xảy ra giữa chừng sẽ làm phiên bản kế tiếp khác -> client tải lại.
	version = get_version(profile)
	walk_in = walk_in_by_profile([profile]).get(profile)
	has_done_at = frappe.get_meta("POS Invoice").has_field("kitchen_done_at")

	base = {"docstatus": 1, "status": "Paid", "pos_profile": profile}
	fields = ["name", "customer", "customer_name", "order_type", "buzzer", "creation"]

	def column(status, extra_fields=()):
		filters = {**base, "custom_kitchen_status": status}
		rows = frappe.get_all(
			"POS Invoice",
			filters=filters,
			fields=fields + list(extra_fields),
			order_by="creation asc",
			limit=MAX_ROWS,
		)
		total = frappe.db.count("POS Invoice", filters) if len(rows) >= MAX_ROWS else len(rows)
		return rows, max(0, total - len(rows))

	preparing, more_preparing = column(PREPARING)
	ready, more_ready = column(READY, ["kitchen_done_at"] if has_done_at else [])
	# Cột phải: thời điểm pha chế bấm "Đã làm", thiếu (đơn cũ) -> lùi về creation.
	for r in ready:
		r["sort_at"] = r.get("kitchen_done_at") or r.creation
	ready.sort(key=lambda r: r["sort_at"])
	for r in preparing:
		r["sort_at"] = r.creation

	_set_buzzer_numbers(preparing + ready)
	# Món của các đơn đang hiện: MỘT truy vấn, đi cùng response (không thêm request phía client).
	items = items_by_invoice([r.name for r in preparing + ready])

	def entry(r):
		lines, hidden = items.get(r.name, ([], 0))
		return {
			"code": short_order_code(r.name),
			"name": "" if walk_in and r.customer == walk_in else short_call_name(r.customer_name),
			"label": order_label(r.order_type, r.get("buzzer_number")),
			"at": str(r["sort_at"]),
			"items": lines,
			"items_more": hidden,
		}

	return {
		"profile": profile,
		"v": version,
		"preparing": [entry(r) for r in preparing],
		"ready": [entry(r) for r in ready],
		"more": {"preparing": more_preparing, "ready": more_ready},
	}
