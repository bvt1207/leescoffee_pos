"""Test s10_variant.load: template ZZTEST (Size) -> biến thể <mã>-M đúng mã / tên / thuộc tính, chạy lại bỏ qua.

Cần Item Attribute "Size" có giá trị "Medium" (abbr M) trên site.
"""
import frappe

from seed import s09_item, s10_variant
from seed.tests._util import check, cleanup, run_load

GROUP, TPL, VAR = "ZZTEST-IG-VAR", "ZZTEST-TPL", "ZZTEST-TPL-M"


def _targets():
    return (("Item", VAR), ("Item", TPL), ("Item Group", GROUP))


def run():
    try:
        cleanup(*_targets())
        root = frappe.db.sql("select name from `tabItem Group` where ifnull(parent_item_group, '') = '' limit 1",
                             pluck=True)[0]
        frappe.get_doc({"doctype": "Item Group", "item_group_name": GROUP, "parent_item_group": root,
                        "is_group": 0}).insert()
        frappe.db.commit()
        run_load(s09_item, [{"item_code": TPL, "item_name": "ZZTEST Template", "item_group": GROUP,
                             "stock_uom": "Nos", "is_stock_item": "0", "is_sales_item": "1",
                             "is_purchase_item": "0", "disabled": "0", "description": "",
                             "has_variants": "1", "attribute": "Size"}])
        rows = [{"item_code": VAR, "item_name": "ZZTEST Template - Size M", "variant_of": TPL,
                 "attribute": "Size", "attribute_value": "Medium", "is_sales_item": "1",
                 "is_purchase_item": "0", "disabled": "0", "description": "ZZTEST biến thể M"}]
        c = run_load(s10_variant, rows, "dry-run")
        check(c["created"] == 1 and not frappe.db.exists("Item", VAR), f"dry-run: {c}")
        c = run_load(s10_variant, rows)
        check(c["created"] == 1, f"lần 1: {c}")
        v = frappe.db.get_value("Item", VAR, ["variant_of", "item_name"], as_dict=True)
        check(v and v.variant_of == TPL and v.item_name == rows[0]["item_name"], f"sai biến thể: {v}")
        flags = frappe.db.get_value("Item", VAR, ["is_sales_item", "is_purchase_item"], as_dict=True)
        check(flags.is_sales_item == 1 and flags.is_purchase_item == 0, f"sai cờ bán / mua: {flags}")
        val = frappe.db.get_value("Item Variant Attribute", {"parent": VAR, "attribute": "Size"}, "attribute_value")
        check(val == "Medium", f"sai thuộc tính: {val}")
        c = run_load(s10_variant, rows)
        check(c["skipped"] == 1 and c["created"] == 0, f"lần 2: {c}")
        print("PASS t_item_variant")
        return "PASS"
    finally:
        cleanup(*_targets())
