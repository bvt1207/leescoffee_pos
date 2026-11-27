"""Giải quyết tùy chọn món (MYPOS Option Group) theo Item / Item Group.

Quy tắc (xem docs/rules/options.md):
- Variant tính theo template (mã template + Item Group của template). Target Item trỏ vào
  mã variant KHÔNG được hỗ trợ.
- Trong một nhóm: lấy dòng target khớp CỤ THỂ NHẤT (Item > Item Group sâu hơn > Item Group cha);
  cùng độ cụ thể thì dòng Loại trừ thắng.
- Giữa các nhóm: hai nhóm trùng `title` hoặc trùng `legacy_field` (khác none) thì chỉ giữ nhóm có
  target cụ thể hơn (cùng độ cụ thể: sort_order nhỏ hơn, rồi tên).
- Phụ thu (2026-11-17): price = extra_price lấy từ DB lúc bán (không tin client), snapshot vào JSON options;
  pos_api._apply_option_surcharge cộng tổng vào một dòng Taxes and Charges kiểu Actual (SAU CTKM).

Cache: chỉ cache CẤU HÌNH nhóm (xóa khi lưu/xóa Option Group). Cây Item Group và Item Group của
món đọc mỗi lần (gom truy vấn) để đổi nhóm hàng có hiệu lực ngay.
"""

import json
import re

import frappe
from frappe import _

CACHE_KEY = "mypos_option_config_v2"  # v2: cấu hình có extra_price (khóa mới để bỏ cache cũ)
LEGACY_FIELDS = ("sugar_level", "ice_level")
LEGACY_VALUES = ("50", "70", "100")  # options của Custom Field Select cũ

# Nhãn hiển thị cho ĐƠN CŨ chỉ có cột sugar_level/ice_level: cột `options` NULL/rỗng (chưa từng ghi JSON).
# `options = '[]'` = đã xử lý, món không có tùy chọn -> KHÔNG dựng từ cột cũ (read_line_options).
# TẠM THỜI — bỏ khi không còn đơn cũ cần hiển thị.
LEGACY_OPTION_LABELS = {"sugar_level": "Đường", "ice_level": "Đá"}

_SPEC_ITEM = (2, 0)  # Item luôn cụ thể hơn mọi Item Group


# ---------------------------------------------------------------------------
# Cấu hình (cache)
# ---------------------------------------------------------------------------


def clear_option_cache():
	frappe.cache.delete_value(CACHE_KEY)


def _load_config():
	cached = frappe.cache.get_value(CACHE_KEY)
	if cached is not None:
		return cached

	groups = frappe.get_all(
		"MYPOS Option Group",
		filters={"enabled": 1},
		fields=["name", "title", "selection_type", "required", "sort_order", "legacy_field"],
		order_by="sort_order asc, name asc",
	)
	names = [g.name for g in groups]
	values, targets = [], []
	if names:
		values = frappe.get_all(
			"MYPOS Option Value",
			filters={"parent": ["in", names], "parenttype": "MYPOS Option Group", "enabled": 1},
			fields=["parent", "label", "is_default", "sort_order", "idx", "extra_price"],
			order_by="parent asc, sort_order asc, idx asc",
		)
		targets = frappe.get_all(
			"MYPOS Option Target",
			filters={"parent": ["in", names], "parenttype": "MYPOS Option Group"},
			fields=["parent", "target_type", "item_group", "item", "include_children", "exclude"],
		)

	by_group = {
		g.name: {
			"name": g.name,
			"title": g.title,
			"selection_type": g.selection_type or "Chọn 1",
			"required": int(g.required or 0),
			"sort_order": int(g.sort_order or 0),
			"legacy_field": g.legacy_field if g.legacy_field in LEGACY_FIELDS else None,
			"values": [],
			"targets": [],
		}
		for g in groups
	}
	for v in values:
		by_group[v.parent]["values"].append(
			{"label": v.label, "is_default": int(v.is_default or 0), "extra_price": max(0.0, float(v.extra_price or 0))}
		)
	for t in targets:
		by_group[t.parent]["targets"].append(
			{
				"type": t.target_type,
				"item_group": t.item_group,
				"item": t.item,
				"include_children": int(t.include_children or 0),
				"exclude": int(t.exclude or 0),
			}
		)

	config = [g for g in by_group.values() if g["values"] and g["targets"]]
	frappe.cache.set_value(CACHE_KEY, config)
	return config


# ---------------------------------------------------------------------------
# Giải quyết nhóm theo món
# ---------------------------------------------------------------------------


def _item_context(item_codes):
	"""{code: {match_code, item_group, item_name}} — variant dùng template. 2 truy vấn."""
	items = frappe.get_all(
		"Item",
		filters={"name": ["in", list(item_codes)]},
		fields=["name", "item_name", "item_group", "variant_of"],
	)
	templates = {i.variant_of for i in items if i.variant_of}
	tmpl_group = {}
	if templates:
		tmpl_group = {
			t.name: t.item_group
			for t in frappe.get_all(
				"Item", filters={"name": ["in", list(templates)]}, fields=["name", "item_group"]
			)
		}
	ctx = {}
	for i in items:
		if i.variant_of:
			ctx[i.name] = {
				"match_code": i.variant_of,
				"item_group": tmpl_group.get(i.variant_of) or i.item_group,
				"item_name": i.item_name or i.name,
			}
		else:
			ctx[i.name] = {"match_code": i.name, "item_group": i.item_group, "item_name": i.item_name or i.name}
	return ctx


def _group_bounds(names):
	if not names:
		return {}
	return {
		g.name: (g.lft, g.rgt)
		for g in frappe.get_all(
			"Item Group", filters={"name": ["in", list(names)]}, fields=["name", "lft", "rgt"]
		)
	}


def _target_spec(target, match_code, item_group, bounds):
	"""Độ cụ thể nếu target khớp món, None nếu không khớp."""
	if target["type"] == "Item":
		return _SPEC_ITEM if target["item"] == match_code else None

	tg = target["item_group"]
	if not tg or not item_group:
		return None
	if tg == item_group:
		return (1, bounds.get(tg, (0, 0))[0])
	if not target["include_children"]:
		return None
	t_b, i_b = bounds.get(tg), bounds.get(item_group)
	if t_b and i_b and t_b[0] < i_b[0] and i_b[1] < t_b[1]:
		return (1, t_b[0])  # tổ tiên sâu hơn có lft lớn hơn
	return None


def _group_spec(group, match_code, item_group, bounds):
	"""Độ cụ thể nếu nhóm áp dụng, None nếu không (hoặc bị loại trừ)."""
	best, excluded = None, False
	for t in group["targets"]:
		spec = _target_spec(t, match_code, item_group, bounds)
		if spec is None:
			continue
		if best is None or spec > best:
			best, excluded = spec, bool(t["exclude"])
		elif spec == best and t["exclude"]:
			excluded = True  # cùng độ cụ thể: exclude thắng
	if best is None or excluded:
		return None
	return best


def _conflict_keys(group):
	keys = {("title", (group["title"] or "").strip().casefold())}
	if group["legacy_field"]:
		keys.add(("legacy", group["legacy_field"]))
	return keys


def resolve_option_groups(item_codes):
	"""{item_code: [group config]} cho cả danh sách — gom truy vấn, không query trong vòng lặp."""
	codes = {c for c in item_codes if c}
	result = {c: [] for c in codes}
	config = _load_config()
	if not codes or not config:
		return result

	ctx = _item_context(codes)
	needed = {c["item_group"] for c in ctx.values() if c["item_group"]}
	needed |= {t["item_group"] for g in config for t in g["targets"] if t["item_group"]}
	bounds = _group_bounds(needed)

	for code, c in ctx.items():
		matched = []
		for g in config:
			spec = _group_spec(g, c["match_code"], c["item_group"], bounds)
			if spec is not None:
				matched.append((spec, g))
		# Trùng title / legacy_field: giữ nhóm cụ thể hơn
		matched.sort(key=lambda x: (tuple(-s for s in x[0]), x[1]["sort_order"], x[1]["name"]))
		taken, kept = set(), []
		for _spec, g in matched:
			keys = _conflict_keys(g)
			if keys & taken:
				continue
			taken |= keys
			kept.append(g)
		kept.sort(key=lambda g: (g["sort_order"], g["name"]))
		result[code] = kept
	return result


def item_names(item_codes):
	return {c: v["item_name"] for c, v in _item_context({c for c in item_codes if c}).items()}


def public_groups(groups):
	"""Payload cho frontend: có extra_price (phụ thu hiển thị), không có targets."""
	return [
		{
			"name": g["name"],
			"title": g["title"],
			"selection_type": g["selection_type"],
			"required": g["required"],
			"values": [
				{"label": v["label"], "is_default": v["is_default"], "extra_price": v.get("extra_price", 0.0)}
				for v in g["values"]
			],
		}
		for g in groups
	]


# ---------------------------------------------------------------------------
# Kiểm tra lựa chọn của một dòng đơn
# ---------------------------------------------------------------------------


def _parse_raw(raw):
	if raw in (None, ""):
		return []
	if isinstance(raw, str):
		try:
			raw = json.loads(raw)
		except Exception:
			frappe.throw(_("Tùy chọn món không đúng định dạng."))
	if not isinstance(raw, list):
		frappe.throw(_("Tùy chọn món không đúng định dạng."))
	return raw


def validate_line_options(raw, groups, item_label):
	"""Kiểm tra options [{group, value}] của một dòng theo các nhóm áp dụng cho món.

	Trả (options_chuẩn_hóa, legacy_columns):
	- options: [{group, group_title, value, price: 0}] theo thứ tự nhóm/giá trị.
	- legacy_columns: {sugar_level|ice_level: "50"|"70"|"100"|""} cho nhóm có legacy_field.
	"""
	by_name = {g["name"]: g for g in groups}
	picked = {}
	for entry in _parse_raw(raw):
		if not isinstance(entry, dict):
			frappe.throw(_("Tùy chọn món không đúng định dạng."))
		gname = (entry.get("group") or "").strip()
		group = by_name.get(gname)
		if not group:
			frappe.throw(
				_("Món {0}: tùy chọn '{1}' không áp dụng cho món này.").format(item_label, gname)
			)
		vals = entry.get("value")
		vals = vals if isinstance(vals, list) else [vals]
		labels = {v["label"] for v in group["values"]}
		for v in vals:
			v = (str(v) if v is not None else "").strip()
			if v not in labels:
				frappe.throw(
					_("Món {0}: giá trị '{1}' không thuộc nhóm '{2}' hoặc đã tắt.").format(
						item_label, v, group["title"]
					)
				)
			bucket = picked.setdefault(gname, [])
			if v not in bucket:
				bucket.append(v)

	options, legacy = [], {}
	for g in groups:
		chosen = picked.get(g["name"], [])
		if g["selection_type"] == "Chọn 1" and len(chosen) > 1:
			frappe.throw(
				_("Món {0}: nhóm '{1}' chỉ được chọn một giá trị.").format(item_label, g["title"])
			)
		if not chosen and g["required"]:
			chosen = [v["label"] for v in g["values"] if v["is_default"]]
			if g["selection_type"] == "Chọn 1":
				chosen = chosen[:1]
			if not chosen:
				frappe.throw(
					_("Món {0}: nhóm '{1}' bắt buộc chọn nhưng chưa chọn và không có giá trị mặc định.").format(
						item_label, g["title"]
					)
				)
		if not chosen:
			continue
		order = [v["label"] for v in g["values"]]
		price_of = {v["label"]: float(v.get("extra_price") or 0) for v in g["values"]}
		chosen.sort(key=order.index)
		for v in chosen:
			# price = phụ thu MỖI ĐƠN VỊ lấy từ cấu hình lúc bán (snapshot), không lấy từ client.
			options.append({"group": g["name"], "group_title": g["title"], "value": v, "price": price_of.get(v, 0.0)})
		if g["legacy_field"]:
			legacy[g["legacy_field"]] = _legacy_number(chosen[0])
	return options, legacy


def _legacy_number(label):
	"""'50%' -> '50'; không thuộc 50/70/100 -> '' (bỏ trống cột cũ, chỉ lưu JSON)."""
	m = re.search(r"\d+", label or "")
	return m.group(0) if m and m.group(0) in LEGACY_VALUES else ""


# ---------------------------------------------------------------------------
# Đọc lại tùy chọn của dòng đã lưu
# ---------------------------------------------------------------------------


def _num(v):
	try:
		return max(0.0, float(v or 0))
	except (TypeError, ValueError):
		return 0.0


def line_surcharge(options_json):
	"""Phụ thu MỖI ĐƠN VỊ của một dòng = tổng price trong JSON options đã lưu (snapshot lúc bán)."""
	if not options_json:
		return 0.0
	try:
		parsed = json.loads(options_json) or []
	except Exception:
		return 0.0
	return sum(_num(o.get("price")) for o in parsed if isinstance(o, dict))


def read_line_options(options_json, sugar_level=None, ice_level=None):
	"""Tùy chọn của một dòng đơn để hiển thị (chỉ đọc) — hàm DUY NHẤT dựng tùy chọn cho mọi API.

	- `options_json` NULL hoặc chuỗi rỗng (đơn cũ, chưa từng ghi JSON) -> dựng từ cột cũ
	  sugar_level / ice_level nếu có giá trị (LEGACY_OPTION_LABELS).
	- Có JSON (kể cả '[]' = đã xử lý, món không có tùy chọn) -> chỉ đọc JSON, không dựng từ cột cũ.
	- JSON hỏng -> [] (không đoán từ cột cũ).
	"""
	if options_json is None or not str(options_json).strip():
		return _legacy_line_options(sugar_level, ice_level)
	try:
		parsed = json.loads(options_json) or []
	except Exception:
		return []
	if isinstance(parsed, list):
		return [
			{
				"group": o.get("group"),
				"group_title": o.get("group_title") or "",
				"value": o.get("value") or "",
				"price": _num(o.get("price")),
			}
			for o in parsed
			if isinstance(o, dict)
		]
	return []


def _legacy_line_options(sugar_level=None, ice_level=None):
	"""Đơn cũ (chưa có JSON options): dựng tùy chọn từ cột sugar_level / ice_level."""
	out = []
	for field, value in (("sugar_level", sugar_level), ("ice_level", ice_level)):
		if value:
			out.append(
				{"group": None, "group_title": LEGACY_OPTION_LABELS[field], "value": f"{value}%", "price": 0}
			)
	return out
