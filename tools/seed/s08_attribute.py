"""Bước 8: Item Attribute "Size". Chỉ kiểm tra: Small = S, Medium = M, Large = L có sẵn (Q1), không sửa thuộc tính."""
import frappe

from seed import config
from seed.common import SeedError, read_csv

TITLE = "Item Attribute (chỉ kiểm tra)"


def load(ctx, rep, rows=None):
    rows = read_csv("variant.csv") if rows is None else rows
    pairs = sorted({(r["attribute"], r["attribute_value"]) for r in rows})
    for attr in sorted({a for a, _ in pairs}):
        if not frappe.db.exists("Item Attribute", attr):
            raise SeedError(f"Chưa có Item Attribute '{attr}' trên site")
    for attr, val in pairs:
        abbr = frappe.db.get_value("Item Attribute Value", {"parent": attr, "parenttype": "Item Attribute",
                                                            "attribute_value": val}, "abbr")
        if not abbr:
            raise SeedError(f"Item Attribute '{attr}' không có giá trị '{val}'")
        expected = config.SIZE_ABBR.get(val)
        if expected and abbr != expected:
            raise SeedError(f"'{attr}={val}' có abbr '{abbr}', cần '{expected}' (mã biến thể <mã>-{expected})")
        rep.add("skipped", f"{attr}={val}", f"abbr {abbr}, không sửa")
    for r in rows:
        abbr = config.SIZE_ABBR.get(r["attribute_value"])
        if abbr and r["item_code"] != f"{r['variant_of']}-{abbr}":
            raise SeedError(f"Biến thể '{r['item_code']}' không theo quy ước {r['variant_of']}-{abbr}")
