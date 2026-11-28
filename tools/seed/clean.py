#!/usr/bin/env python3
"""Làm sạch DATA/ ("Data Test.xlsx" + CSV tồn đầu kỳ) -> tools/seed/clean/*.csv + report.txt.

Không cần frappe, không ghi site. Có lỗi -> không ghi file nào, thoát mã 1.
Không in / không xuất họ tên, SĐT, email của khách thành viên / doanh nghiệp.

Chạy:  python tools/seed/clean.py [--data-dir DATA] [--out tools/seed/clean]
"""
import argparse
import csv
import re
import sys
import unicodedata
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SEED_DIR.parent))  # thư mục tools/

from seed import config  # noqa: E402

try:
    import openpyxl
except ImportError:  # pragma: no cover
    sys.exit("Thiếu openpyxl: pip install openpyxl (hoặc chạy bằng ~/frappe-bench/env/bin/python)")

REPO_DIR = SEED_DIR.parents[1]


class Reporter:
    def __init__(self):
        self.errors, self.warnings, self.infos = [], [], []

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def info(self, msg):
        self.infos.append(msg)

    def text(self):
        out = []
        for title, items in (("LỖI", self.errors), ("CẢNH BÁO", self.warnings), ("THÔNG TIN", self.infos)):
            out.append(f"== {title} ({len(items)})")
            out.extend(f"  - {m}" for m in items)
        return "\n".join(out) + "\n"


# --- tiện ích -----------------------------------------------------------------

def s(v):
    return "" if v is None else unicodedata.normalize("NFC", str(v)).strip()


def num(v):
    return None if s(v) == "" else float(v)


def flag(v):
    return int(num(v) or 0)


def fmt(v):
    if v is None:
        return ""
    return str(int(v)) if float(v).is_integer() else repr(float(v))


def base(name):
    """Bỏ hậu tố công ty " - LC" của file nguồn."""
    return re.sub(config.SOURCE_SUFFIX_RE, "", s(name))


_LABEL_RE = re.compile(r"(?i)\bchi nhánh\s+(" + "|".join(re.escape(v) for v in config.BRANCH_LABEL.values()) + r")\b")
_KEY_BY_LABEL = {v.lower(): k for k, v in config.BRANCH_LABEL.items()}


def rename(text):
    """'Chi nhánh A' -> 'Chi nhánh LC Nguyễn Huệ' (Q5). Trả (tên mới, khóa chi nhánh hoặc '').

    Idempotent: tên đã mang nhãn mới giữ nguyên (token A/B/C chỉ khớp chữ cái đơn ngay sau "chi nhánh"),
    khóa chi nhánh vẫn nhận ra từ nhãn mới. Chấp nhận cả file cũ (A/B/C) lẫn file đã đổi tên.
    """
    keys = []

    def sub(m):
        k = m.group(2).upper()
        keys.append(k)
        return f"{m.group(1)} {config.BRANCH_LABEL[k]}"

    out = re.sub(config.BRANCH_TOKEN_RE, sub, s(text))
    if not keys:
        m = _LABEL_RE.search(out)
        if m:
            keys.append(_KEY_BY_LABEL[m.group(1).lower()])
    return out, (keys[0] if keys else "")


def norm_uom(u):
    u = s(u)
    return config.UOM_MAP.get(u.lower(), u)


def same_company(a, b):
    return s(a).replace("’", "'").lower() == s(b).replace("’", "'").lower()


def sheet_rows(wb, name, rep):
    if name not in wb.sheetnames:
        rep.error(f"Thiếu sheet '{name}'")
        return []
    rows = list(wb[name].iter_rows(values_only=True))
    if not rows:
        return []
    header = [s(c) for c in rows[0]]
    out = []
    for idx, r in enumerate(rows[1:], start=2):
        if not any(s(c) for c in r):
            continue
        d = {h: (r[i] if i < len(r) else None) for i, h in enumerate(header) if h}
        d["_row"] = idx
        out.append(d)
    return out


def unique(rep, seen, key, where):
    if key in seen:
        rep.error(f"{where}: trùng '{key}'")
        return False
    seen.add(key)
    return True


# --- từng phần ----------------------------------------------------------------

def file_company(wb, rep):
    rows = sheet_rows(wb, config.SHEET_COMPANY, rep)
    name = s(rows[0].get("Công ty")) if rows else ""
    rep.info(f"Company trong file: '{name}' -> KHÔNG nạp; loader dùng Company của site (có thể khác dấu nháy)")
    return name


def clean_branch(wb, rep):
    out, seen = [], set()
    for r in sheet_rows(wb, config.SHEET_BRANCH, rep):
        name, key = rename(r.get("Branch"))
        if not key:
            rep.error(f"Branch dòng {r['_row']}: '{s(r.get('Branch'))}' không nhận ra chi nhánh A/B/C")
            continue
        if unique(rep, seen, key, f"Branch dòng {r['_row']}"):
            out.append({"key": key, "branch": name})
    missing = set(config.BRANCH_KEYS) - seen
    if missing:
        rep.error(f"Sheet Branch thiếu chi nhánh {sorted(missing)}")
    rep.info("Đổi tên chi nhánh (Q5): " + "; ".join(f"Chi nhánh {b['key']} -> {b['branch']}" for b in out))
    return out


def clean_cost_center(wb, rep, company):
    out, seen = [], set()
    for r in sheet_rows(wb, config.SHEET_COST_CENTER, rep):
        name, key = rename(r.get("Cost Center Name"))
        parent = base(r.get("Parent Cost Center"))
        where = f"Cost center dòng {r['_row']}"
        if same_company(parent, company):
            parent = ""  # gốc Cost Center của Company trên site
        else:
            rep.error(f"{where}: cha '{parent}' không phải gốc Company; chưa hỗ trợ")
        if flag(r.get("Is Group")):
            rep.error(f"{where}: Cost Center nhóm chưa hỗ trợ")
        if unique(rep, seen, name, where):
            out.append({"key": key, "cost_center_name": name, "parent": parent})
    return out


def clean_account(wb, rep):
    out, seen = [], set()
    for r in sheet_rows(wb, config.SHEET_ACCOUNT, rep):
        name, key = rename(r.get("Account Name"))
        where = f"Account dòng {r['_row']} ({name})"
        if flag(r.get("Is Group")):
            rep.error(f"{where}: tài khoản nhóm chưa hỗ trợ")
        if not unique(rep, seen, name, where):
            continue
        out.append({"key": key, "account_name": name, "parent_account": base(r.get("Parent Account")),
                    "account_type": s(r.get("Account Type")), "root_type": s(r.get("Root Type")),
                    "currency": s(r.get("Currency"))})
    return out


def clean_warehouse(wb, rep, accounts):
    acc = {a["account_name"]: a for a in accounts}
    out, groups, seen = [], set(), set()
    for sheet in config.SHEET_WAREHOUSES:
        for r in sheet_rows(wb, sheet, rep):
            name, key = rename(r.get("Warehouse Name"))
            parent, _ = rename(base(r.get("Parent Warehouse")))
            account, _ = rename(base(r.get("Account")))
            is_group = flag(r.get("Is Group Warehouse"))
            where = f"{sheet} dòng {r['_row']} ({name})"
            if parent == config.ROOT_WAREHOUSE_BASE:
                parent = ""
            elif parent not in groups:
                rep.error(f"{where}: kho cha '{parent}' chưa khai báo (phải là kho nhóm ở sheet trước)")
            if account and (account not in acc or acc[account]["account_type"] != "Stock"):
                rep.error(f"{where}: tài khoản kho '{account}' không có trong sheet Account hoặc không phải loại Stock")
            if not is_group and not account:
                rep.warn(f"{where}: kho không gắn tài khoản, dùng tài khoản kho mặc định của Company")
            if not unique(rep, seen, name, where):
                continue
            if is_group:
                groups.add(name)
            out.append({"key": key, "warehouse_name": name, "parent": parent, "is_group": is_group,
                        "account": account})
    for k in config.BRANCH_KEYS:
        if sum(1 for w in out if w["key"] == k and not w["is_group"]) != 1:
            rep.error(f"Chi nhánh {k}: cần đúng 1 kho con (không phải nhóm)")
    return out


def clean_mode_of_payment(wb, rep, accounts):
    acc = {a["account_name"]: a for a in accounts}
    out, seen = [], set()
    for r in sheet_rows(wb, config.SHEET_MODE_OF_PAYMENT, rep):
        name, key = rename(r.get("Mode of Payment"))
        account, _ = rename(base(r.get("Default Account (Accounts)")))
        mtype = s(r.get("Type"))
        if mtype == "Bank" and name.startswith(config.LEGACY_BANK_MODE_PREFIX):
            new = config.BANK_MODE_PREFIX + name[len(config.LEGACY_BANK_MODE_PREFIX):]
            rep.info(f"Mode of Payment file cũ '{name}' -> '{new}'")
            name = new
        where = f"Mode of payment dòng {r['_row']} ({name})"
        if mtype not in ("Cash", "Bank", "General", "Phone"):
            rep.error(f"{where}: Type '{mtype}' không hợp lệ")
        if account not in acc:
            rep.error(f"{where}: tài khoản '{account}' không có trong sheet Account")
        elif acc[account]["account_type"] not in ("Bank", "Cash", "Receivable"):
            rep.error(f"{where}: tài khoản '{account}' phải loại Bank / Cash / Receivable (ERPNext bắt buộc)")
        elif mtype in ("Cash", "Bank") and acc[account]["account_type"] != mtype:
            rep.warn(f"{where}: Type {mtype} nhưng tài khoản loại {acc[account]['account_type']}")
        if unique(rep, seen, name, where):
            out.append({"key": key, "mode_of_payment": name, "type": mtype,
                        "enabled": flag(r.get("Enabled")), "account": account})
    for k in config.BRANCH_KEYS:
        types = sorted(m["type"] for m in out if m["key"] == k)
        if types != sorted(config.MODE_TYPES_PER_BRANCH):
            rep.error(f"Chi nhánh {k}: cần đúng các Mode of Payment loại {list(config.MODE_TYPES_PER_BRANCH)}, có {types}")
    for m in out:
        if m["type"] == "Bank" and not m["mode_of_payment"].startswith(config.BANK_MODE_PREFIX):
            rep.error(f"Mode of Payment loại Bank phải bắt đầu bằng '{config.BANK_MODE_PREFIX}': '{m['mode_of_payment']}'")
    rep.info(f"Mode of Payment: {len(out)} ({', '.join(m['mode_of_payment'] for m in out)})")
    return out


def clean_uom(wb, rep):
    out = {}
    for r in sheet_rows(wb, config.SHEET_UOM, rep):
        raw = s(r.get("UOM Name"))
        if not raw:
            rep.error(f"UOM dòng {r['_row']}: thiếu tên")
            continue
        name = norm_uom(raw)
        if name != raw:
            rep.info(f"UOM '{raw}' -> '{name}' (dạng có sẵn trên site; không sửa Symbol của UOM site)")
        if name in out:
            rep.warn(f"UOM '{name}' lặp (dòng {r['_row']}), giữ dòng đầu")
            continue
        out[name] = {"uom": name, "symbol": s(r.get("Symbol")),
                     "must_be_whole_number": flag(r.get("Must be Whole Number")),
                     "source": "site" if name in config.SITE_UOMS else "new"}
    return out


def add_site_uom(rep, uoms, name, who):
    if name in uoms:
        return True
    if name in config.SITE_UOMS:
        uoms[name] = {"uom": name, "symbol": "", "must_be_whole_number": 0, "source": "site"}
        rep.info(f"UOM '{name}' ({who} dùng) không có trong sheet UOM; dùng bản có sẵn trên site")
        return True
    return False


def clean_tree(wb, rep, sheets, name_col, parent_col, root):
    out = {}
    for sheet in sheets:
        for r in sheet_rows(wb, sheet, rep):
            name, parent = s(r.get(name_col)), s(r.get(parent_col))
            where = f"{sheet} dòng {r['_row']} ({name})"
            if not name or not parent:
                rep.error(f"{where}: thiếu tên hoặc nhóm cha")
                continue
            if name in out:
                rep.error(f"{where}: trùng")
                continue
            if parent != root:
                if parent not in out:
                    rep.error(f"{where}: nhóm cha '{parent}' chưa khai báo trước")
                elif not out[parent]["is_group"]:
                    rep.error(f"{where}: nhóm cha '{parent}' không phải nhóm")
            out[name] = {"name": name, "parent": parent, "is_group": flag(r.get("Is Group"))}
    return out


def clean_items(wb, rep, uoms, groups):
    out = {}
    for r in sheet_rows(wb, config.SHEET_ITEM, rep):
        code = s(r.get("Item Code"))
        where = f"Item dòng {r['_row']} ({code or '?'})"
        if not code:
            rep.error(f"{where}: thiếu Item Code")
            continue
        if code in out:
            rep.error(f"{where}: trùng mã")
            continue
        it = {
            "item_code": code, "item_name": s(r.get("Item Name")), "item_group": s(r.get("Item Group")),
            "stock_uom": norm_uom(r.get("Default Unit of Measure")),
            "is_stock_item": flag(r.get("Maintain Stock")), "is_sales_item": flag(r.get("Allow Sales")),
            "is_purchase_item": flag(r.get("Allow Purchase")), "disabled": flag(r.get("Disabled")),
            "description": s(r.get("Description")), "has_variants": flag(r.get("Has Variants")),
            "attribute": s(r.get("Attribute (Variant Attributes)")),
            "image": s(r.get("Image")),
        }
        if not it["item_name"]:
            rep.error(f"{where}: thiếu Item Name")
        g = groups.get(it["item_group"])
        if not g:
            rep.error(f"{where}: Item Group '{it['item_group']}' không có trong sheet Item group")
        elif g["is_group"]:
            rep.warn(f"{where}: Item Group '{it['item_group']}' là nhóm cha; giữ nguyên (Q7)")
        if not add_site_uom(rep, uoms, it["stock_uom"], code):
            rep.error(f"{where}: UOM '{it['stock_uom']}' không có trong sheet UOM / UOM site")
        if it["has_variants"]:
            if it["attribute"] != config.SIZE_ATTRIBUTE:
                rep.error(f"{where}: Has Variants = 1 nhưng thuộc tính '{it['attribute']}'")
            if it["is_stock_item"]:
                rep.error(f"{where}: template không được quản lý kho")
        elif it["attribute"]:
            rep.warn(f"{where}: có thuộc tính nhưng Has Variants = 0 (bỏ thuộc tính)")
            it["attribute"] = ""
        out[code] = it
    n_img = sum(1 for i in out.values() if i["image"])
    rep.info(f"Ảnh Item: {n_img} có link, {len(out) - n_img} thiếu -> nạp nguyên URL vào field image (quyết định 7)")
    return out


def clean_variants(wb, rep, items):
    out, pairs = {}, set()
    for r in sheet_rows(wb, config.SHEET_VARIANT, rep):
        code = s(r.get("Item Code"))
        where = f"Biến thể dòng {r['_row']} ({code or '?'})"
        tpl, attr, val = s(r.get("Variant Of")), s(r.get("Attribute (Variant Attributes)")), \
            s(r.get("Attribute Value (Variant Attributes)"))
        if not code or code in out or code in items:
            rep.error(f"{where}: thiếu hoặc trùng mã")
            continue
        t = items.get(tpl)
        if not t or not t["has_variants"]:
            rep.error(f"{where}: '{tpl}' không phải template trong sheet Item")
            continue
        if attr != config.SIZE_ATTRIBUTE or val not in config.SIZE_ABBR:
            rep.error(f"{where}: thuộc tính '{attr}={val}' không hợp lệ (cần Size = {list(config.SIZE_ABBR)})")
            continue
        expected = f"{tpl}-{config.SIZE_ABBR[val]}"
        if code != expected:
            rep.error(f"{where}: mã phải là '{expected}'")
        if (tpl, val) in pairs:
            rep.error(f"{where}: '{tpl}' đã có biến thể {val}")
        pairs.add((tpl, val))
        if norm_uom(r.get("Default Unit of Measure")) != t["stock_uom"]:
            rep.error(f"{where}: UOM khác template")
        if s(r.get("Item Group")) != t["item_group"]:
            rep.warn(f"{where}: Item Group khác template")
        if flag(r.get("Maintain Stock")):
            rep.error(f"{where}: biến thể đồ uống không được quản lý kho (template không quản lý kho)")
        out[code] = {"item_code": code, "item_name": s(r.get("Item Name")), "variant_of": tpl,
                     "attribute": attr, "attribute_value": val,
                     "is_sales_item": flag(r.get("Allow Sales")), "is_purchase_item": flag(r.get("Allow Purchase")),
                     "disabled": flag(r.get("Disabled")), "description": s(r.get("Description")),
                     "image": s(r.get("Image"))}
    for code, t in items.items():
        if t["has_variants"]:
            have = {v["attribute_value"] for v in out.values() if v["variant_of"] == code}
            missing = [v for v in config.SIZE_ABBR if v not in have]
            if missing:
                rep.warn(f"Template '{code}' thiếu biến thể {missing}")
    no_img = [c for c, v in out.items() if not v["image"]]
    rep.info(f"Ảnh biến thể: {len(out) - len(no_img)} có link riêng, {len(no_img)} thiếu"
             + (f" {no_img} (không tự lấy ảnh template; xem ERPNext có kế thừa không)" if no_img else ""))
    return out


def clean_price_lists(wb, rep):
    out = {}
    for r in sheet_rows(wb, config.SHEET_PRICE_LIST, rep):
        name, key = rename(r.get("Price List Name"))
        where = f"Price list dòng {r['_row']} ({name})"
        buying, selling = flag(r.get("Buying")), flag(r.get("Selling"))
        if buying == selling:
            rep.error(f"{where}: phải là đúng một trong Buying / Selling")
        if name in out:
            rep.error(f"{where}: trùng")
            continue
        out[name] = {"key": key, "price_list": name, "currency": s(r.get("Currency")), "buying": buying,
                     "selling": selling, "enabled": flag(r.get("Enabled"))}
    return out


def clean_prices(wb, rep, items, variants, price_lists):
    allitems = {**{c: i for c, i in items.items()}, **variants}
    out, seen = [], set()
    for sheet, kind in ((config.SHEET_SELLING, "selling"), (config.SHEET_BUYING, "buying")):
        for r in sheet_rows(wb, sheet, rep):
            code = s(r.get("Item Code"))
            pl, _ = rename(r.get("Price List"))
            rate = num(r.get("Rate"))
            where = f"{sheet} dòng {r['_row']} ({code} @ {pl})"
            p = price_lists.get(pl)
            if not p:
                rep.error(f"{where}: Price List không có trong sheet Price list")
                continue
            if not p[kind]:
                rep.error(f"{where}: Price List không phải loại {kind}")
            it = allitems.get(code)
            if not it:
                rep.error(f"{where}: mã không có trong Item / biến thể")
                continue
            if it.get("has_variants"):
                rep.error(f"{where}: gắn giá vào template")
                continue
            uom = norm_uom(r.get("UOM"))
            stock_uom = it.get("stock_uom") or items[it["variant_of"]]["stock_uom"]
            if uom and uom != stock_uom:
                rep.error(f"{where}: UOM '{uom}' khác UOM của mã '{stock_uom}'")
            if rate is None or rate <= 0:
                rep.error(f"{where}: giá không hợp lệ")
                continue
            cur = s(r.get("Currency")) or p["currency"]
            if cur != p["currency"]:
                rep.error(f"{where}: tiền tệ '{cur}' khác Price List '{p['currency']}'")
            flag_name = "is_sales_item" if kind == "selling" else "is_purchase_item"
            if not it.get(flag_name):
                rep.warn(f"{where}: mã có {flag_name} = 0 nhưng có giá {kind}")
            if (code, pl) in seen:
                rep.error(f"{where}: trùng")
                continue
            seen.add((code, pl))
            out.append({"item_code": code, "price_list": pl, "rate": fmt(rate), "currency": cur,
                        "uom": stock_uom, "kind": kind})
    sellable = [c for c, i in allitems.items() if i.get("is_sales_item") and not i.get("has_variants")]
    for p in price_lists.values():
        if p["selling"]:
            miss = [c for c in sellable if (c, p["price_list"]) not in seen]
            if miss:
                rep.warn(f"Price List '{p['price_list']}' thiếu giá bán cho {miss}")
    return out


def clean_customer(wb, rep, cgroups):
    rows = sheet_rows(wb, config.SHEET_CUSTOMER, rep)
    contact_cols = [h for h in (rows[0].keys() if rows else []) if
                    any(k in h for k in ("Email", "Phone", "Mobile", "First Name", "Last Name"))]
    cands = [r for r in rows if s(r.get("Customer Group")) == config.WALK_IN_CUSTOMER_GROUP
             and s(r.get("Customer Type")) == "Individual" and not any(s(r.get(c)) for c in contact_cols)]
    if len(cands) != 1:
        rep.error(f"Không xác định được đúng 1 khách vãng lai (nhóm '{config.WALK_IN_CUSTOMER_GROUP}', "
                  f"không có liên hệ): {len(cands)} dòng")
        return []
    c = cands[0]
    if config.WALK_IN_CUSTOMER_GROUP not in cgroups:
        rep.error(f"Customer Group '{config.WALK_IN_CUSTOMER_GROUP}' không có trong sheet Customer group")
    out = [{"customer_name": s(c.get("Customer Name")), "customer_type": "Individual",
            "customer_group": config.WALK_IN_CUSTOMER_GROUP, "territory": config.WALK_IN_TERRITORY}]
    rep.info(f"Customer: chỉ nạp '{out[0]['customer_name']}' (Territory {config.WALK_IN_TERRITORY}, Q8; "
             f"file ghi '{s(c.get('Territory'))}'); {len(rows) - 1} dòng khác là khách mẫu (bước s15)")
    return out


def clean_opening_stock(path, rep, items, warehouses):
    leaf = {w["key"]: w["warehouse_name"] for w in warehouses if not w["is_group"]}
    out, seen, totals = [], set(), {}
    if not path.exists():
        rep.error(f"Không thấy {path}")
        return out
    with open(path, encoding="utf-8-sig", newline="") as f:
        for i, r in enumerate(csv.DictReader(f), start=2):
            code = s(r.get("Item Code (item_code)"))
            wh_raw = s(r.get("Warehouse (warehouse)"))
            wh, key = rename(base(wh_raw))
            where = f"{path.name} dòng {i} ({code} @ {wh_raw})"
            if key not in leaf:
                rep.error(f"{where}: không nhận ra kho chi nhánh")
                continue
            if wh.lower() != leaf[key].lower():
                rep.error(f"{where}: kho '{wh}' khác kho chi nhánh '{leaf[key]}'")
            # chỉ khác hoa / thường ("Kho Chi nhánh" vs "Kho chi nhánh") -> dùng tên trong sheet Warehouse
            it = items.get(code)
            if not it:
                rep.error(f"{where}: mã không có trong sheet Item")
                continue
            if it["has_variants"] or not it["is_stock_item"]:
                rep.error(f"{where}: món không quản lý kho hoặc là template")
                continue
            uom = norm_uom(r.get("Stock UOM (stock_uom)"))
            if uom != it["stock_uom"]:
                rep.error(f"{where}: UOM '{uom}' khác UOM của Item '{it['stock_uom']}'")
            qty, rate = num(r.get("Quantity (qty)")), num(r.get("Valuation Rate (valuation_rate)"))
            if qty is None or qty <= 0 or rate is None or rate < 0:
                rep.error(f"{where}: số lượng / giá vốn không hợp lệ")
                continue
            if (key, code) in seen:
                rep.error(f"{where}: trùng mã trong cùng kho")
                continue
            seen.add((key, code))
            totals[key] = totals.get(key, 0) + qty * rate
            out.append({"warehouse_key": key, "item_code": code, "qty": fmt(qty), "uom": uom,
                        "valuation_rate": fmt(rate)})
    stock_items = [c for c, it in items.items() if it["is_stock_item"] and not it["has_variants"]]
    for k in config.BRANCH_KEYS:
        miss = [c for c in stock_items if (k, c) not in seen]
        if miss:
            rep.warn(f"Kho chi nhánh {k} không có tồn đầu kỳ cho {miss}")
    rep.info("Tồn đầu kỳ (CSV): " + "; ".join(f"{leaf.get(k, k)}: {sum(1 for o in out if o['warehouse_key'] == k)} mã, "
                                              f"giá trị {totals.get(k, 0):,.0f}" for k in config.BRANCH_KEYS))
    return out


def clean_product_bundle(wb, rep, items, variants):
    allitems = {**items, **variants}
    out, parent, parents = [], None, set()
    for r in sheet_rows(wb, config.SHEET_PRODUCT_BUNDLE, rep):
        if s(r.get("Parent Item")):
            parent = s(r.get("Parent Item"))
            parents.add(parent)
        code, qty, uom = s(r.get("Item (Items)")), num(r.get("Qty (Items)")), norm_uom(r.get("UOM (Items)"))
        where = f"Product Bundle dòng {r['_row']} ({parent} <- {code})"
        p, c = allitems.get(parent), items.get(code)
        if not p or p.get("has_variants") or p.get("is_stock_item"):
            rep.error(f"{where}: món cha phải là mã bán được, không quản lý kho, không phải template")
            continue
        if not c or not c["is_stock_item"]:
            rep.error(f"{where}: thành phần phải là Item quản lý kho")
            continue
        if uom != c["stock_uom"]:
            rep.error(f"{where}: UOM '{uom}' khác UOM của thành phần '{c['stock_uom']}'")
        if qty is None or qty <= 0:
            rep.error(f"{where}: số lượng không hợp lệ")
            continue
        out.append({"parent_item": parent, "item_code": code, "qty": fmt(qty), "uom": uom})
    rep.info(f"Product Bundle: {len(parents)} món, {len(out)} dòng -> xuất product_bundle.csv, CHƯA nạp (Q4)")
    return out


def clean_demo_customers(wb, rep, cgroups):
    """Khách mẫu (cờ with_demo_customers): mọi dòng trừ khách vãng lai; email bắt buộc @example.com."""
    rows = sheet_rows(wb, config.SHEET_CUSTOMER, rep)
    out = []
    for r in rows:
        if s(r.get("Customer Group")) == config.WALK_IN_CUSTOMER_GROUP:
            continue
        where = f"Customer dòng {r['_row']}"
        email = s(r.get("Email Address (Contact)")).lower()
        if not email.endswith("@" + config.DEMO_EMAIL_DOMAIN):
            rep.error(f"{where}: khách mẫu phải có email @{config.DEMO_EMAIL_DOMAIN} (không nạp dữ liệu thật)")
            continue
        if s(r.get("Customer Group")) not in cgroups:
            rep.error(f"{where}: Customer Group '{s(r.get('Customer Group'))}' không có trong sheet Customer group")
        out.append({
            "customer_name": s(r.get("Customer Name")), "customer_type": s(r.get("Customer Type")),
            "customer_group": s(r.get("Customer Group")), "territory": s(r.get("Territory")),
            "first_name": s(r.get("First Name (Contact)")), "last_name": s(r.get("Last Name (Contact)")),
            "email": email, "designation": s(r.get("Designation (Contact)")),
            "phone": s(r.get("Phone (Contact)")), "mobile_no": s(r.get("Mobile No (Contact)")),
            "is_primary_contact": flag(r.get("Is Primary Contact (Contact)")),
        })
    kinds = {}
    for c in out:
        kinds[c["customer_group"]] = kinds.get(c["customer_group"], 0) + 1
    rep.info(f"Khách mẫu (bước s15, nạp khi with_demo_customers=1 — lệnh trong README bật cờ): {len(out)} khách {kinds}, "
             f"email @{config.DEMO_EMAIL_DOMAIN}")
    return out


def clean_suppliers(wb, rep):
    """Nhóm NCC + NCC (cờ with_suppliers)."""
    groups = clean_tree(wb, rep, (config.SHEET_SUPPLIER_GROUP,), "Supplier Group Name", "Parent Supplier Group",
                        config.ROOT_SUPPLIER_GROUP)
    out, seen = [], set()
    for r in sheet_rows(wb, config.SHEET_SUPPLIER, rep):
        name, grp = s(r.get("Supplier Name")), s(r.get("Supplier Group"))
        where = f"Supplier dòng {r['_row']} ({name})"
        if grp not in groups:
            rep.error(f"{where}: Supplier Group '{grp}' không có trong sheet Supplier group")
        if unique(rep, seen, name, where):
            out.append({"supplier_name": name, "supplier_type": s(r.get("Supplier Type")), "supplier_group": grp,
                        "country": s(r.get("Country")), "default_currency": s(r.get("Billing Currency")),
                        "disabled": flag(r.get("Disabled"))})
    rep.info(f"Nhà cung cấp (bước s16, nạp khi with_suppliers=1 — lệnh trong README bật cờ): "
             f"{len(groups)} nhóm, {len(out)} NCC")
    return groups, out


def ice_note(rep, opening, bundles, warehouses):
    """Chỉ cảnh báo: số ly tối đa theo tồn đá viên mỗi kho (định mức nhỏ nhất / lớn nhất trong Product Bundle)."""
    per_cup = [float(b["qty"]) for b in bundles if b["item_code"] == config.ICE_ITEM]
    if not per_cup:
        return
    leaf = {w["key"]: w["warehouse_name"] for w in warehouses if not w["is_group"]}
    parts = []
    for o in opening:
        if o["item_code"] == config.ICE_ITEM:
            q = float(o["qty"])
            parts.append(f"{leaf.get(o['warehouse_key'])}: {fmt(q)} {o['uom']} ~ {int(q // max(per_cup))}-"
                         f"{int(q // min(per_cup))} ly")
    rep.warn(f"Đá viên {config.ICE_ITEM} ({fmt(min(per_cup))}-{fmt(max(per_cup))} / ly theo Product Bundle): "
             + "; ".join(parts) + ". Khi bật Product Bundle, POS chặn bán khi hết đá (không sửa dữ liệu).")


def check_urls(rep, items, variants, timeout=8):
    """Thử truy cập link ảnh (HEAD, lỗi thì GET). Chỉ cảnh báo."""
    import urllib.request

    urls = {}
    for code, it in {**items, **variants}.items():
        if it.get("image"):
            urls.setdefault(it["image"], []).append(code)
    bad = []
    for url, codes in urls.items():
        why = ""
        for method in ("HEAD", "GET"):
            try:
                req = urllib.request.Request(url, method=method, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    ctype = resp.headers.get("Content-Type", "")
                    if resp.status < 400 and (not ctype or ctype.startswith("image/")):
                        why = ""
                        break
                    why = f"HTTP {resp.status}, Content-Type {ctype or '?'}"
            except Exception as e:  # noqa: BLE001
                why = type(e).__name__ + ": " + str(e)[:80]
        if why:
            bad.append((codes, why))
    for codes, why in bad:
        rep.warn(f"Link ảnh không truy cập được ({why}): {', '.join(codes)}")
    rep.info(f"Kiểm tra link ảnh: {len(urls)} URL khác nhau, {len(urls) - len(bad)} OK, {len(bad)} lỗi")


def write_csv(path, rows, fields):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", default=str(REPO_DIR / "DATA"))
    ap.add_argument("--out", default=str(SEED_DIR / "clean"))
    ap.add_argument("--check-urls", action="store_true", help="thử truy cập link ảnh (cần mạng)")
    a = ap.parse_args(argv)
    data_dir, out_dir = Path(a.data_dir), Path(a.out)
    found = [data_dir / n for n in config.XLSX_FILES if (data_dir / n).exists()]
    if len(found) != 1:
        sys.exit(f"Cần đúng 1 file trong {list(config.XLSX_FILES)} ở {data_dir}, tìm thấy {[f.name for f in found]}")
    xlsx = found[0]

    rep = Reporter()
    rep.info(f"File nguồn: {xlsx.name}")
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    company = file_company(wb, rep)
    branches = clean_branch(wb, rep)
    cost_centers = clean_cost_center(wb, rep, company)
    accounts = clean_account(wb, rep)
    warehouses = clean_warehouse(wb, rep, accounts)
    mops = clean_mode_of_payment(wb, rep, accounts)
    uoms = clean_uom(wb, rep)
    igroups = clean_tree(wb, rep, config.SHEET_ITEM_GROUPS, "Item Group Name", "Parent Item Group",
                         config.ROOT_ITEM_GROUP)
    items = clean_items(wb, rep, uoms, igroups)
    variants = clean_variants(wb, rep, items)
    price_lists = clean_price_lists(wb, rep)
    prices = clean_prices(wb, rep, items, variants, price_lists)
    cgroups = clean_tree(wb, rep, (config.SHEET_CUSTOMER_GROUP,), "Customer Group Name", "Parent Customer Group",
                         config.ROOT_CUSTOMER_GROUP)
    customers = clean_customer(wb, rep, cgroups)
    opening = clean_opening_stock(data_dir / config.OPENING_CSV_FILE, rep, items, warehouses)
    bundles = clean_product_bundle(wb, rep, items, variants)
    demo_customers = clean_demo_customers(wb, rep, cgroups)
    sgroups, suppliers = clean_suppliers(wb, rep)
    ice_note(rep, opening, bundles, warehouses)
    if a.check_urls:
        check_urls(rep, items, variants)

    used = {config.SHEET_COMPANY, config.SHEET_BRANCH, config.SHEET_COST_CENTER, config.SHEET_ACCOUNT,
            config.SHEET_MODE_OF_PAYMENT, *config.SHEET_WAREHOUSES, config.SHEET_UOM, *config.SHEET_ITEM_GROUPS,
            config.SHEET_ITEM, config.SHEET_VARIANT, config.SHEET_PRICE_LIST, config.SHEET_SELLING,
            config.SHEET_BUYING, config.SHEET_CUSTOMER_GROUP, config.SHEET_CUSTOMER, config.SHEET_PRODUCT_BUNDLE,
            config.SHEET_SUPPLIER_GROUP, config.SHEET_SUPPLIER}
    rep.info("Sheet bỏ qua (không nạp): " + "; ".join(n for n in wb.sheetnames if n not in used))
    unused = [u for u, d in uoms.items() if d["source"] == "new" and
              not any(i["stock_uom"] == u for i in items.values())]
    if unused:
        rep.info(f"UOM chưa món nào dùng (vẫn tạo): {unused}")
    rep.info(f"Đếm: UOM {len(uoms)}, Item Group {len(igroups)}, Branch {len(branches)}, Cost Center {len(cost_centers)}, "
             f"Account {len(accounts)}, Warehouse {len(warehouses)}, Mode of Payment {len(mops)}, Item {len(items)} "
             f"(template {sum(i['has_variants'] for i in items.values())}), biến thể {len(variants)}, "
             f"Price List {len(price_lists)}, giá bán {sum(p['kind'] == 'selling' for p in prices)}, "
             f"giá mua {sum(p['kind'] == 'buying' for p in prices)}, Customer Group {len(cgroups)}, "
             f"Customer {len(customers)} vãng lai + {len(demo_customers)} khách mẫu, "
             f"Supplier Group {len(sgroups)}, Supplier {len(suppliers)}, "
             f"dòng tồn đầu kỳ {len(opening)}, dòng Product Bundle {len(bundles)}")

    text = rep.text()
    print(text)
    if rep.errors:
        print("CÓ LỖI -> không ghi file nào.")
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.csv"):
        old.unlink()  # chỉ trong thư mục đầu ra clean/ (gitignore); tránh sót CSV của bộ dữ liệu cũ
    W = lambda f, rows, cols: write_csv(out_dir / f, rows, cols)  # noqa: E731
    W("uom.csv", uoms.values(), ["uom", "symbol", "must_be_whole_number", "source"])
    W("item_group.csv", [{"item_group": g["name"], "parent_item_group": g["parent"], "is_group": g["is_group"]}
                         for g in igroups.values()], ["item_group", "parent_item_group", "is_group"])
    W("branch.csv", branches, ["key", "branch"])
    W("cost_center.csv", cost_centers, ["key", "cost_center_name", "parent"])
    W("account.csv", accounts, ["key", "account_name", "parent_account", "account_type", "root_type", "currency"])
    W("warehouse.csv", warehouses, ["key", "warehouse_name", "parent", "is_group", "account"])
    W("mode_of_payment.csv", mops, ["key", "mode_of_payment", "type", "enabled", "account"])
    W("item.csv", items.values(), ["item_code", "item_name", "item_group", "stock_uom", "is_stock_item",
                                   "is_sales_item", "is_purchase_item", "disabled", "description", "has_variants",
                                   "attribute", "image"])
    W("variant.csv", variants.values(), ["item_code", "item_name", "variant_of", "attribute", "attribute_value",
                                         "is_sales_item", "is_purchase_item", "disabled", "description", "image"])
    W("price_list.csv", price_lists.values(), ["key", "price_list", "currency", "buying", "selling", "enabled"])
    W("price.csv", prices, ["item_code", "price_list", "rate", "currency", "uom", "kind"])
    W("customer_group.csv", [{"customer_group": g["name"], "parent_customer_group": g["parent"],
                              "is_group": g["is_group"]} for g in cgroups.values()],
      ["customer_group", "parent_customer_group", "is_group"])
    W("customer.csv", customers, ["customer_name", "customer_type", "customer_group", "territory"])
    W("opening_stock.csv", opening, ["warehouse_key", "item_code", "qty", "uom", "valuation_rate"])
    W("product_bundle.csv", bundles, ["parent_item", "item_code", "qty", "uom"])
    W("demo_customer.csv", demo_customers, ["customer_name", "customer_type", "customer_group", "territory",
                                            "first_name", "last_name", "email", "designation", "phone",
                                            "mobile_no", "is_primary_contact"])
    W("supplier_group.csv", [{"supplier_group": g["name"], "parent_supplier_group": g["parent"],
                              "is_group": g["is_group"]} for g in sgroups.values()],
      ["supplier_group", "parent_supplier_group", "is_group"])
    W("supplier.csv", suppliers, ["supplier_name", "supplier_type", "supplier_group", "country",
                                  "default_currency", "disabled"])
    (out_dir / "report.txt").write_text(text, encoding="utf-8")
    print(f"Đã ghi {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
