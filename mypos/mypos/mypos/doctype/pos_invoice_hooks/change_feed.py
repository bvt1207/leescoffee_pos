"""Bộ đếm thay đổi theo POS Profile (Redis) — màn POS chỉ tải lại danh sách khi số này đổi (2026-11-25).

- Khóa `mypos_chg:<pos_profile>` (theo site, KHÔNG TTL): số nguyên. Thiếu khóa (Redis restart / bị xóa) -> khởi tạo bằng số
  ngẫu nhiên lớn (SET NX) -> client so BẰNG / KHÁC thấy khác -> tải lại, không sót đơn.
- `bump(profile)` tăng sau khi giao dịch commit (rollback -> không tăng): POS Invoice `on_change` (mọi save / submit / cancel /
  update_after_submit / db_set, kể cả insert), `order_cancel.cancel_draft` (set_value không chạy hook), POS Opening / Closing Entry.
- Chỉ đọc / ghi Redis; lỗi chỉ ghi Error Log, không chặn bán hàng.
- Giai đoạn 3 (2026-11-25): sau khi tăng, publish_realtime REALTIME_EVENT tới phòng "all" (mọi System User đang kết nối, quyết định D2-i),
  payload CHỈ {p: tên POS Profile, v: phiên bản} — không dữ liệu đơn / khách / tiền; client tự lọc theo profile của mình.
  Socket lỗi -> bỏ qua (client vẫn poll phiên bản). `docs/rules/realtime.md` §5.
"""

import secrets

import frappe

COUNTER_PREFIX = "mypos_chg:"
REALTIME_EVENT = "mypos_pos_changed"
# POS Profile của user cho get_pos_changes (đọc DB một lần, giữ ngắn; lưu POS Profile -> xóa hết).
PROFILE_CACHE_PREFIX = "mypos_user_profile:"
PROFILE_CACHE_SECONDS = 300


def _key(name):
	return frappe.cache.make_key(name)


def _seed(key):
	"""Khởi tạo số ngẫu nhiên khi thiếu khóa (không đè giá trị đang có)."""
	frappe.cache.set(key, secrets.randbelow(10**12) * 1000, nx=True)


def get_version(profile):
	"""Phiên bản hiện tại (chuỗi) của POS Profile — chỉ đọc Redis."""
	key = _key(COUNTER_PREFIX + profile)
	raw = frappe.cache.get(key)
	if raw is None:
		_seed(key)
		raw = frappe.cache.get(key)
	return raw.decode() if isinstance(raw, bytes) else str(raw)


def _incr(profile):
	try:
		key = _key(COUNTER_PREFIX + profile)
		_seed(key)
		version = frappe.cache.incr(key)
	except Exception:
		frappe.log_error(title="MYPOS: không tăng được phiên bản thay đổi", message=frappe.get_traceback())
		return
	_publish(profile, version)


def _publish(profile, version):
	"""Báo realtime phòng "all" (truyền room rõ ràng: trong job nền Frappe mặc định gửi vào phòng task)."""
	try:
		from frappe.realtime import get_site_room

		frappe.publish_realtime(REALTIME_EVENT, {"p": profile, "v": str(version)}, room=get_site_room())
	except Exception:
		# Socket / Redis pub-sub không chạy -> client vẫn nhận qua poll phiên bản.
		pass


def bump(profile):
	"""Tăng phiên bản của POS Profile SAU commit (self-test: frappe.flags.mypos_chg_immediate -> tăng ngay)."""
	if not profile:
		return
	if frappe.flags.get("mypos_chg_immediate"):
		_incr(profile)
		return
	hooks = getattr(frappe.db, "after_commit", None)
	if hooks is not None and hasattr(hooks, "add"):
		hooks.add(lambda p=profile: _incr(p))
	else:
		_incr(profile)


def on_doc_change(doc, method=None):
	"""doc_events on_change: POS Invoice, POS Opening Entry, POS Closing Entry (đều có field pos_profile)."""
	bump(doc.get("pos_profile"))


# ---------------------------------------------------------------------------
# POS Profile của user (cache cho get_pos_changes)
# ---------------------------------------------------------------------------


def cached_profile_of_user(resolver):
	"""POS Profile của user hiện tại: cache Redis PROFILE_CACHE_SECONDS; lỗi (throw) không cache."""
	key = PROFILE_CACHE_PREFIX + frappe.session.user
	name = frappe.cache.get_value(key)
	if name:
		return name
	name = resolver()
	frappe.cache.set_value(key, name, expires_in_sec=PROFILE_CACHE_SECONDS)
	return name


def clear_profile_cache(doc=None, method=None):
	"""doc_events POS Profile on_update / on_trash: đổi Applicable for Users / bật tắt -> xóa cache của mọi user.

	Xóa ngay và xóa lại sau commit (request khác có thể đã cache giá trị cũ trong lúc giao dịch chưa commit).
	"""
	_delete_profile_cache()
	hooks = getattr(frappe.db, "after_commit", None)
	if hooks is not None and hasattr(hooks, "add"):
		hooks.add(_delete_profile_cache)


def _delete_profile_cache():
	try:
		frappe.cache.delete_keys(PROFILE_CACHE_PREFIX)
	except Exception:
		frappe.log_error(title="MYPOS: không xóa được cache POS Profile của user", message=frappe.get_traceback())
