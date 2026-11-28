"""Bước 12: Item Price bán + mua theo Price List chi nhánh. Khóa: (item_code, price_list), chỉ giá chung
(không theo khách / nhà cung cấp / lô)."""
import frappe

from seed.common import SeedError, read_csv, require, to_float

TITLE = "Item Price"


def _existing(code, price_list):
    rows = frappe.get_all("Item Price", filters={"item_code": code, "price_list": price_list},
                          fields=["name", "price_list_rate", "customer", "supplier", "batch_no"])
    return [p for p in rows if not (p.customer or p.supplier or p.batch_no)]


def _price_list(ctx, name, cache):
    if name not in cache:
        info = frappe.db.get_value("Price List", name, ["currency", "selling", "buying", "enabled"], as_dict=True)
        if not info and ("Price List", name) in ctx.planned:
            info = None  # dry-run: sẽ tạo ở bước 11, chưa đọc được cờ
        elif not info:
            raise SeedError(f"Chưa có Price List '{name}'")
        cache[name] = info
    return cache[name]


def load(ctx, rep, rows=None):
    rows = read_csv("price.csv") if rows is None else rows
    cache = {}
    for r in rows:
        code, pl, kind = r["item_code"], r["price_list"], r.get("kind") or ""
        rate, currency = to_float(r["rate"]), r["currency"]
        key = f"{code} @ {pl}"
        require(ctx, "Item", code, key)
        require(ctx, "Price List", pl, key)
        info = _price_list(ctx, pl, cache)
        if info:
            if not info.enabled:
                raise SeedError(f"{key}: Price List đang tắt")
            if kind and not info.get(kind):
                raise SeedError(f"{key}: Price List không phải loại {kind}")
            if info.currency != currency:
                raise SeedError(f"{key}: tiền tệ '{currency}' khác Price List ({info.currency})")

        in_db = ctx.in_db("Item", code)
        if in_db:
            it = frappe.db.get_value("Item", code, ["has_variants", "stock_uom"], as_dict=True)
            if it.has_variants:
                raise SeedError(f"{key}: không gắn giá vào template")
            if r.get("uom") and r["uom"] != it.stock_uom:
                raise SeedError(f"{key}: UOM '{r['uom']}' khác UOM của Item '{it.stock_uom}'")
        existing = _existing(code, pl) if in_db else []
        if len(existing) > 1:
            raise SeedError(f"{key}: có {len(existing)} Item Price chung, không biết sửa dòng nào")
        if not existing:
            if ctx.apply:
                frappe.get_doc({"doctype": "Item Price", "item_code": code, "price_list": pl,
                                "price_list_rate": rate, "currency": currency,
                                "uom": r.get("uom") or frappe.db.get_value("Item", code, "stock_uom")}).insert()
            rep.add("created", key, f"{rate:,.0f} {currency}")
        elif abs((existing[0].price_list_rate or 0) - rate) > 0.001:
            if ctx.apply:
                doc = frappe.get_doc("Item Price", existing[0].name)
                doc.price_list_rate = rate
                doc.save()
            rep.add("updated", key, f"{existing[0].price_list_rate:,.0f} -> {rate:,.0f}")
        else:
            rep.add("skipped", key, f"{rate:,.0f}")
