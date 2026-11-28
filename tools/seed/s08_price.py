"""Bước 8: Item Price bán (Standard Selling) + mua (Standard Buying). Khóa: (item_code, price_list),
chỉ xét giá chung (không theo khách / nhà cung cấp / lô)."""
import frappe

from seed.common import SeedError, read_csv, require, to_float

TITLE = "Item Price"


def _existing(code, price_list):
    rows = frappe.get_all("Item Price", filters={"item_code": code, "price_list": price_list},
                          fields=["name", "price_list_rate", "currency", "customer", "supplier", "batch_no"])
    return [p for p in rows if not (p.customer or p.supplier or p.batch_no)]


def load(ctx, rep, rows=None):
    rows = read_csv("price.csv") if rows is None else rows
    pl_cache = {}
    for r in rows:
        code, pl, kind = r["item_code"], r["price_list"], r["kind"]
        rate, currency = to_float(r["rate"]), r["currency"]
        key = f"{code} @ {pl}"
        require(ctx, "Item", code, key)

        if pl not in pl_cache:
            pl_cache[pl] = frappe.db.get_value("Price List", pl, ["currency", "selling", "buying", "enabled"],
                                               as_dict=True)
        info = pl_cache[pl]
        if not info:
            raise SeedError(f"{key}: chưa có Price List '{pl}'")
        if not info.enabled:
            raise SeedError(f"{key}: Price List '{pl}' đang tắt")
        if not info.get(kind):
            raise SeedError(f"{key}: Price List '{pl}' không phải loại {kind}")
        if info.currency != currency:
            raise SeedError(f"{key}: tiền tệ '{currency}' khác Price List ({info.currency})")

        if ctx.in_db("Item", code) and frappe.db.get_value("Item", code, "has_variants"):
            raise SeedError(f"{key}: không gắn giá vào template")

        existing = _existing(code, pl) if ctx.in_db("Item", code) else []
        if len(existing) > 1:
            raise SeedError(f"{key}: có {len(existing)} Item Price chung, không biết sửa dòng nào")
        if not existing:
            if ctx.apply:
                frappe.get_doc({"doctype": "Item Price", "item_code": code, "price_list": pl,
                                "price_list_rate": rate, "currency": currency,
                                "uom": frappe.db.get_value("Item", code, "stock_uom")}).insert()
            rep.add("created", key, f"{rate:,.0f} {currency}")
        elif abs((existing[0].price_list_rate or 0) - rate) > 0.001:
            if ctx.apply:
                doc = frappe.get_doc("Item Price", existing[0].name)
                doc.price_list_rate = rate
                doc.save()
            rep.add("updated", key, f"{existing[0].price_list_rate:,.0f} -> {rate:,.0f}")
        else:
            rep.add("skipped", key, f"{rate:,.0f}")
