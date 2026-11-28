#!/usr/bin/env python3
"""Làm sạch DATA/ -> tools/seed/clean/*.csv + report.txt. Không cần frappe, không ghi site.

Chạy:  python tools/seed/clean.py [--data-dir DATA] [--out tools/seed/clean]
Có lỗi -> không ghi file nào, thoát mã 1.
Không in / không xuất SĐT, email, mã số thuế của khách.
"""
import argparse
import csv
import re
import sys
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


def s(v):
    return "" if v is None else str(v).strip()


def num(v):
    if v is None or s(v) == "":
        return None
    return float(v)


def fmt(v):
    """Số -> chuỗi gọn (100.0 -> '100')."""
    if v is None:
        return ""
    return str(int(v)) if float(v).is_integer() else repr(float(v))


def strip_suffix(name):
    return re.sub(config.SOURCE_SUFFIX_RE, "", s(name))


def norm_uom(u):
    u = s(u)
    return config.UOM_MAP.get(u.lower(), u)


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


# --- từng phần ---------------------------------------------------------------

def clean_uom(wb, rep):
    out = {}
    for r in sheet_rows(wb, config.SHEET_UOM, rep):
        raw = s(r.get("UOM Name"))
        if not raw:
            rep.error(f"UOM dòng {r['_row']}: thiếu tên")
            continue
        name = norm_uom(raw)
        if name != raw:
            rep.info(f"UOM '{raw}' -> '{name}' (dạng có sẵn trên site, Q3)")
        whole = int(num(r.get("Must be Whole Number")) or 0)
        if name in out:
            rep.warn(f"UOM '{name}' lặp trong sheet (dòng {r['_row']}), giữ dòng đầu")
            continue
        out[name] = {"uom": name, "must_be_whole_number": whole,
                     "source": "site" if name in config.SITE_UOMS else "new"}
    for name, whole in config.EXTRA_UOMS.items():
        if name not in out:
            out[name] = {"uom": name, "must_be_whole_number": whole, "source": "new"}
            rep.info(f"UOM '{name}' thêm mới (Item đang dùng, sheet UOM thiếu)")
    return out


def clean_item_group(wb, rep):
    out = {}
    for r in sheet_rows(wb, config.SHEET_ITEM_GROUP, rep):
        name, parent = s(r.get("Item Group Name")), s(r.get("Parent Item Group"))
        if not name or not parent:
            rep.error(f"Item group dòng {r['_row']}: thiếu tên hoặc nhóm cha")
            continue
        if name in out:
            rep.error(f"Item group '{name}' lặp (dòng {r['_row']})")
            continue
        out[name] = {"item_group": name, "parent_item_group": parent,
                     "is_group": int(num(r.get("Is Group")) or 0)}
    # nhóm cha phải là gốc của site hoặc khai báo trước nó
    seen = set()
    for name, g in out.items():
        p = g["parent_item_group"]
        if p in out and p not in seen:
            rep.error(f"Item group '{name}': nhóm cha '{p}' khai báo sau nhóm con")
        if p in out and not out[p]["is_group"]:
            rep.error(f"Item group '{name}': nhóm cha '{p}' không phải nhóm (Is Group = 0)")
        seen.add(name)
    return out


def clean_branch_warehouse(wb, rep):
    for r in sheet_rows(wb, config.SHEET_WAREHOUSE, rep):
        src = strip_suffix(r.get("Warehouse Name"))
        parent = strip_suffix(r.get("Parent Warehouse"))
        key = config.SOURCE_WAREHOUSE_KEY.get(src)
        if not key:
            rep.error(f"Kho nguồn '{src}' không có trong SOURCE_WAREHOUSE_KEY")
            continue
        rep.info(f"Kho nguồn '{src}' -> '{config.WAREHOUSES[key]}' (nhóm '{config.WAREHOUSE_GROUP}', nguồn ghi '{parent}')")
    branches = [{"key": k, "branch": config.BRANCHES[k]} for k in config.BRANCH_KEYS]
    warehouses = [{"key": "", "warehouse_name": config.WAREHOUSE_GROUP, "parent": "", "is_group": 1}]
    warehouses += [{"key": k, "warehouse_name": config.WAREHOUSES[k], "parent": config.WAREHOUSE_GROUP,
                    "is_group": 0} for k in config.BRANCH_KEYS]
    return branches, warehouses


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
        item = {
            "item_code": code,
            "item_name": s(r.get("Item Name")),
            "item_group": s(r.get("Item Group")),
            "stock_uom": norm_uom(r.get("Default Unit of Measure")),
            "is_stock_item": int(num(r.get("Maintain Stock")) or 0),
            "material_request_type": s(r.get("Default Material Request Type")),
            "has_variants": int(num(r.get("Has Variants")) or 0),
            "attribute": s(r.get("Attribute (Variant Attributes)")),
        }
        if not item["item_name"]:
            rep.error(f"{where}: thiếu Item Name")
        if not item["item_group"]:
            rep.error(f"{where}: thiếu Item Group")
        elif item["item_group"] not in groups:
            rep.error(f"{where}: Item Group '{item['item_group']}' không có trong sheet Item group")
        elif groups[item["item_group"]]["is_group"]:
            rep.warn(f"{where}: Item Group '{item['item_group']}' là nhóm cha")
        if not item["stock_uom"]:
            rep.error(f"{where}: thiếu UOM")
        elif item["stock_uom"] not in uoms:
            rep.error(f"{where}: UOM '{item['stock_uom']}' không có trong danh sách UOM")
        if item["has_variants"] and item["attribute"] != config.SIZE_ATTRIBUTE:
            rep.error(f"{where}: Has Variants = 1 nhưng thuộc tính là '{item['attribute']}' (cần '{config.SIZE_ATTRIBUTE}')")
        if not item["has_variants"] and item["attribute"]:
            rep.warn(f"{where}: có thuộc tính '{item['attribute']}' nhưng Has Variants = 0 (bỏ thuộc tính)")
            item["attribute"] = ""
        if item["stock_uom"] == "Kg" and re.search(r"\d+\s*g\b", item["item_name"], re.I):
            rep.warn(f"{where}: UOM Kg nhưng tên ghi theo gram ('{item['item_name']}'); giữ Kg (Q12)")
        out[code] = item
    used = {i["item_group"] for i in out.values()}
    for g in groups.values():
        if not g["is_group"] and g["item_group"] not in used:
            rep.info(f"Item Group '{g['item_group']}' chưa có món nào (vẫn tạo)")
    return out


def clean_variants(wb, rep, items):
    out = {}
    pairs = set()
    for r in sheet_rows(wb, config.SHEET_VARIANT, rep):
        code = s(r.get("Item Code"))
        where = f"Variant dòng {r['_row']} ({code or '?'})"
        tpl = s(r.get("Variant Of (Variant Attributes)"))
        attr = s(r.get("Attribute (Variant Attributes)"))
        raw_val = s(r.get("Attribute Value (Variant Attributes)"))
        val = config.SIZE_VALUE_MAP.get(raw_val.lower())
        if not code:
            rep.error(f"{where}: thiếu Item Code")
            continue
        if code in out or code in items:
            rep.error(f"{where}: trùng mã")
            continue
        t = items.get(tpl)
        if not t:
            rep.error(f"{where}: template '{tpl}' không có trong sheet Item")
            continue
        if not t["has_variants"]:
            rep.error(f"{where}: '{tpl}' không phải template (Has Variants = 0)")
        if attr != config.SIZE_ATTRIBUTE:
            rep.error(f"{where}: thuộc tính '{attr}' (cần '{config.SIZE_ATTRIBUTE}')")
        if not val:
            rep.error(f"{where}: giá trị size '{raw_val}' không có trong SIZE_VALUE_MAP")
            continue
        expected = f"{tpl}-{config.SIZE_ABBR[val]}"
        if code != expected:
            rep.error(f"{where}: mã phải theo quy ước <mã>-<abbr> = '{expected}'")
        if (tpl, val) in pairs:
            rep.error(f"{where}: '{tpl}' đã có biến thể {val}")
        pairs.add((tpl, val))
        uom = norm_uom(r.get("Default Unit of Measure"))
        if uom != t["stock_uom"]:
            rep.error(f"{where}: UOM '{uom}' khác template '{t['stock_uom']}'")
        group = s(r.get("Item Group"))
        if group != t["item_group"]:
            rep.warn(f"{where}: Item Group '{group}' khác template; dùng nhóm của template")
        stock = int(num(r.get("Maintain Stock")) or 0)
        if stock != t["is_stock_item"]:
            rep.warn(f"{where}: Maintain Stock khác template; dùng giá trị template")
        out[code] = {"item_code": code, "item_name": s(r.get("Item Name")), "variant_of": tpl,
                     "attribute": config.SIZE_ATTRIBUTE, "attribute_value": val}
    for code, t in items.items():
        if t["has_variants"]:
            have = {v["attribute_value"] for v in out.values() if v["variant_of"] == code}
            for val in config.SIZE_ABBR:
                if val not in have:
                    rep.warn(f"Template '{code}' thiếu biến thể {val}")
    rep.info("Giá trị size trong sheet ('Size M' / 'Size L') -> 'Medium' / 'Large' có sẵn trên site (Q5)")
    return out


def clean_prices(wb, rep, items, variants):
    sellable = {c for c, i in items.items() if not i["has_variants"]} | set(variants)
    out = []
    keys = set()
    for sheet, kind in ((config.SHEET_SELLING, "selling"), (config.SHEET_BUYING, "buying")):
        for r in sheet_rows(wb, sheet, rep):
            code, pl = s(r.get("Item Code")), s(r.get("Price List"))
            where = f"{sheet} dòng {r['_row']} ({code or '?'})"
            rate, cur = num(r.get("Rate")), s(r.get("Currency"))
            if code in items and items[code]["has_variants"]:
                rep.error(f"{where}: gắn giá vào template; giá phải theo từng size")
                continue
            if code not in sellable:
                rep.error(f"{where}: mã không có trong sheet Item / Variant")
                continue
            if not pl:
                rep.error(f"{where}: thiếu Price List")
                continue
            if rate is None or rate <= 0:
                rep.error(f"{where}: giá không hợp lệ ({r.get('Rate')})")
                continue
            if not cur:
                rep.error(f"{where}: thiếu Currency")
                continue
            if (code, pl) in keys:
                rep.error(f"{where}: trùng (mã, Price List)")
                continue
            keys.add((code, pl))
            out.append({"item_code": code, "price_list": pl, "rate": fmt(rate), "currency": cur, "kind": kind})
    for code in variants:
        if not any(p["item_code"] == code and p["kind"] == "selling" for p in out):
            rep.warn(f"Biến thể '{code}' chưa có giá bán")
    return out


def check_price_conflicts(wb, rep, prices, variants):
    main = {(p["item_code"], p["price_list"]): float(p["rate"]) for p in prices}
    by_tpl = {}
    for code, v in variants.items():
        by_tpl.setdefault(v["variant_of"], []).append(code)
    for sheet in config.PRICE_CONFLICT_SHEETS:
        if sheet not in wb.sheetnames:
            continue
        n_diff = 0
        for r in sheet_rows(wb, sheet, rep):
            code, pl, rate = s(r.get("Item Code")), s(r.get("Price List")), num(r.get("Rate"))
            if not code or rate is None:
                continue
            if (code, pl) in main:
                if abs(main[(code, pl)] - rate) > 0.5:
                    n_diff += 1
                    rep.warn(f"Giá lệch ({sheet}): {code} = {fmt(rate)}, bản chính = {fmt(main[(code, pl)])}")
            elif code in by_tpl:
                sizes = {c: main.get((c, pl)) for c in sorted(by_tpl[code])}
                hit = [c for c, v in sizes.items() if v is not None and abs(v - rate) <= 0.5]
                n_diff += 1
                detail = ", ".join(f"{c}={fmt(v)}" for c, v in sizes.items())
                if hit:
                    rep.warn(f"Giá gắn template ({sheet}): {code} = {fmt(rate)} (trùng giá {hit[0]}; bản chính: {detail})")
                else:
                    rep.warn(f"Giá mâu thuẫn ({sheet}): {code} = {fmt(rate)} không khớp size nào ({detail})")
            else:
                n_diff += 1
                rep.warn(f"Giá ({sheet}): {code} / {pl} không có trong bản chính")
        rep.info(f"Sheet '{sheet}': không nạp, {n_diff} dòng lệch / không có trong bản chính")


def clean_customer(wb, rep):
    rows = sheet_rows(wb, config.SHEET_CUSTOMER, rep)
    cands = [r for r in rows if s(r.get("Customer Type")) == "Individual"
             and not s(r.get("Mobile No")) and not s(r.get("Email Id")) and not s(r.get("Tax ID"))]
    if len(cands) != 1:
        rep.error(f"Không xác định được đúng 1 khách vãng lai (Individual, không SĐT / email / MST): {len(cands)} dòng")
        return []
    c = cands[0]
    out = [{"customer_name": s(c.get("Customer Name")), "customer_type": "Individual",
            "customer_group": s(c.get("Customer Group")) or "Individual",
            "territory": s(c.get("Territory"))}]
    if not out[0]["territory"]:
        rep.error("Khách vãng lai thiếu Territory")
    rep.info(f"Customer: chỉ nạp '{out[0]['customer_name']}'; bỏ {len(rows) - 1} dòng khác "
             "(đại lý / khách cá nhân có dữ liệu liên hệ, không in ra)")
    return out


def clean_opening_stock(wb, rep, items):
    rows = sheet_rows(wb, config.OPENING_STOCK_SHEET, rep)
    lines, seen, src = [], set(), set()
    for r in rows:
        code = s(r.get("Item Code (Items)"))
        if not code:
            continue
        where = f"{config.OPENING_STOCK_SHEET} dòng {r['_row']} ({code})"
        if s(r.get("Target Warehouse (Items)")):
            src.add(strip_suffix(r.get("Target Warehouse (Items)")))
        it = items.get(code)
        qty, rate = num(r.get("Qty (Items)")), num(r.get("Basic Rate (as per Stock UOM) (Items)"))
        uom = norm_uom(r.get("Stock UOM (Items)"))
        if not it:
            rep.error(f"{where}: mã không có trong sheet Item")
            continue
        if it["has_variants"] or not it["is_stock_item"]:
            rep.error(f"{where}: món không quản lý kho hoặc là template")
            continue
        if uom != it["stock_uom"]:
            rep.error(f"{where}: UOM '{uom}' khác UOM của Item '{it['stock_uom']}'")
        if qty is None or qty <= 0:
            rep.error(f"{where}: số lượng không hợp lệ")
            continue
        if rate is None or rate < 0:
            rep.error(f"{where}: giá vốn không hợp lệ")
            continue
        if code in seen:
            rep.error(f"{where}: trùng mã")
            continue
        seen.add(code)
        lines.append((code, qty, rate))
    for code, it in items.items():
        if it["is_stock_item"] and not it["has_variants"] and code not in seen:
            rep.warn(f"Món quản lý kho '{code}' không có tồn đầu kỳ")
    out = [{"warehouse_key": k, "item_code": c, "qty": fmt(q), "valuation_rate": fmt(v)}
           for k in config.BRANCH_KEYS for c, q, v in lines]
    total = sum(q * v for _, q, v in lines)
    rep.info(f"Tồn đầu kỳ: sheet '{config.OPENING_STOCK_SHEET}' (kho nguồn: {', '.join(sorted(src))}), "
             f"{len(lines)} mã x {len(config.BRANCH_KEYS)} kho (Q6), giá trị mỗi kho {total:,.0f}")
    return out


def build_stock_mapping(path, rep, items, prices):
    if not path.exists():
        rep.warn(f"Không thấy {path.name}; bỏ qua stock_mapping.csv")
        return []
    buy = {p["item_code"]: float(p["rate"]) for p in prices if p["kind"] == "buying"}
    stock_items = [c for c, i in items.items() if i["is_stock_item"] and not i["has_variants"]]
    data = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            code = s(r.get("Item Code (item_code)"))
            if not code:
                continue
            key = config.SOURCE_WAREHOUSE_KEY.get(strip_suffix(r.get("Warehouse (warehouse)")))
            if not key:
                rep.warn(f"{path.name}: kho '{r.get('Warehouse (warehouse)')}' không nhận ra")
                continue
            d = data.setdefault(code, {"uom": norm_uom(r.get("Stock UOM (stock_uom)")), "rates": set(), "qty": {}})
            d["rates"].add(num(r.get("Valuation Rate (valuation_rate)")))
            d["qty"][key] = num(r.get("Quantity (qty)"))
    overlap = set(data) & (set(items))
    rep.info(f"{path.name}: {len(data)} mã, giao với sheet Item = {len(overlap)}; KHÔNG nạp (Q6, Q7)")
    out, claimed = [], {}
    for code, d in data.items():
        uom, factor = d["uom"], 1
        if uom in config.UOM_FACTOR:
            uom, factor = config.UOM_FACTOR[uom]
        note = []
        if len(d["rates"]) > 1:
            note.append("giá vốn khác nhau giữa các kho")
        rate = sorted(r for r in d["rates"] if r is not None)[0] if d["rates"] else None
        rate_item = rate * factor if rate is not None else None
        cands = [c for c in stock_items if items[c]["stock_uom"] == uom and c in buy
                 and rate_item is not None and abs(buy[c] - rate_item) <= 0.5]
        for c in cands:
            claimed.setdefault(c, []).append(code)
        out.append({
            "csv_item_code": code, "csv_uom": d["uom"], "csv_valuation_rate": fmt(rate),
            "item_uom": uom, "rate_per_item_uom": fmt(rate_item),
            **{f"qty_{k}": fmt(d["qty"].get(k)) for k in config.BRANCH_KEYS},
            "candidates": ";".join(cands),
            "match": "one" if len(cands) == 1 else ("multiple" if cands else "none"),
            "approved_item_code": "", "note": "; ".join(note),
        })
    for row in out:
        shared = [c for c in row["candidates"].split(";") if c and len(claimed.get(c, [])) > 1]
        if shared:
            row["note"] = "; ".join(filter(None, [row["note"], "ứng viên trùng với mã CSV khác: " + ",".join(shared)]))
    cnt = {m: sum(1 for r in out if r["match"] == m) for m in ("one", "multiple", "none")}
    rep.info(f"stock_mapping.csv: khớp 1 ứng viên {cnt['one']}, nhiều ứng viên {cnt['multiple']}, "
             f"không có ứng viên {cnt['none']} (so theo UOM + giá mua quy đổi; bằng chứng yếu)")
    return out


def write_csv(path, rows, fields):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", default=str(REPO_DIR / "DATA"))
    ap.add_argument("--out", default=str(SEED_DIR / "clean"))
    a = ap.parse_args(argv)
    data_dir, out_dir = Path(a.data_dir), Path(a.out)
    xlsx = data_dir / config.XLSX_FILE
    if not xlsx.exists():
        sys.exit(f"Không thấy {xlsx}")

    rep = Reporter()
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    uoms = clean_uom(wb, rep)
    groups = clean_item_group(wb, rep)
    branches, warehouses = clean_branch_warehouse(wb, rep)
    items = clean_items(wb, rep, uoms, groups)
    variants = clean_variants(wb, rep, items)
    prices = clean_prices(wb, rep, items, variants)
    check_price_conflicts(wb, rep, prices, variants)
    customers = clean_customer(wb, rep)
    opening = clean_opening_stock(wb, rep, items)
    mapping = build_stock_mapping(data_dir / config.OPENING_CSV_FILE, rep, items, prices)

    used = {config.SHEET_UOM, config.SHEET_ITEM_GROUP, config.SHEET_WAREHOUSE, config.SHEET_ITEM,
            config.SHEET_VARIANT, config.SHEET_SELLING, config.SHEET_BUYING, config.SHEET_CUSTOMER,
            config.OPENING_STOCK_SHEET, *config.PRICE_CONFLICT_SHEETS}
    dropped = [n for n in wb.sheetnames if n not in used]
    rep.info("Sheet bỏ qua (không nạp): " + "; ".join(dropped))
    rep.info(f"Đếm: UOM {len(uoms)}, Item Group {len(groups)}, Branch {len(branches)}, Warehouse {len(warehouses)}, "
             f"Item {len(items)}, Variant {len(variants)}, "
             f"giá bán {sum(p['kind'] == 'selling' for p in prices)}, giá mua {sum(p['kind'] == 'buying' for p in prices)}, "
             f"Customer {len(customers)}, dòng tồn đầu kỳ {len(opening)}")

    text = rep.text()
    print(text)
    if rep.errors:
        print("CÓ LỖI -> không ghi file nào.")
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "uom.csv", uoms.values(), ["uom", "must_be_whole_number", "source"])
    write_csv(out_dir / "item_group.csv", groups.values(), ["item_group", "parent_item_group", "is_group"])
    write_csv(out_dir / "branch.csv", branches, ["key", "branch"])
    write_csv(out_dir / "warehouse.csv", warehouses, ["key", "warehouse_name", "parent", "is_group"])
    write_csv(out_dir / "item.csv", items.values(),
              ["item_code", "item_name", "item_group", "stock_uom", "is_stock_item", "material_request_type",
               "has_variants", "attribute"])
    write_csv(out_dir / "variant.csv", variants.values(),
              ["item_code", "item_name", "variant_of", "attribute", "attribute_value"])
    write_csv(out_dir / "price.csv", prices, ["item_code", "price_list", "rate", "currency", "kind"])
    write_csv(out_dir / "customer.csv", customers, ["customer_name", "customer_type", "customer_group", "territory"])
    write_csv(out_dir / "opening_stock.csv", opening, ["warehouse_key", "item_code", "qty", "valuation_rate"])
    write_csv(out_dir / "stock_mapping.csv", mapping,
              ["csv_item_code", "csv_uom", "csv_valuation_rate", "item_uom", "rate_per_item_uom",
               *[f"qty_{k}" for k in config.BRANCH_KEYS], "candidates", "match", "approved_item_code", "note"])
    (out_dir / "report.txt").write_text(text, encoding="utf-8")
    print(f"Đã ghi {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
