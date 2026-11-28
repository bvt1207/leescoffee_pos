"""Bước 7: Item Variant theo Size (mã <template>-M / -L, tên lấy theo sheet)."""
import frappe

from seed.common import SeedError, read_csv, require

TITLE = "Item Variant"


def _variant_with_value(template, attribute, value):
    rows = frappe.db.sql(
        """select v.name from `tabItem` v
           join `tabItem Variant Attribute` a on a.parent = v.name and a.parenttype = 'Item'
           where v.variant_of = %s and a.attribute = %s and a.attribute_value = %s""",
        (template, attribute, value), pluck=True)
    return rows


def load(ctx, rep, rows=None):
    rows = read_csv("variant.csv") if rows is None else rows
    for r in rows:
        code, tpl, attr, val = r["item_code"], r["variant_of"], r["attribute"], r["attribute_value"]
        require(ctx, "Item", tpl, f"Biến thể '{code}'")

        cur = frappe.db.get_value("Item", code, ["variant_of", "item_name"], as_dict=True)
        if cur:
            if cur.variant_of != tpl:
                raise SeedError(f"Item '{code}' đã có nhưng variant_of = '{cur.variant_of}', cần '{tpl}'")
            have = frappe.db.get_value("Item Variant Attribute", {"parent": code, "parenttype": "Item",
                                                                  "attribute": attr}, "attribute_value")
            if have != val:
                raise SeedError(f"Biến thể '{code}' có {attr} = '{have}', cần '{val}' (không tự sửa)")
            if cur.item_name != r["item_name"]:
                if ctx.apply:
                    doc = frappe.get_doc("Item", code)
                    doc.item_name = r["item_name"]
                    doc.save()
                rep.add("updated", code, f"item_name -> {r['item_name']}")
            else:
                rep.add("skipped", code)
            continue

        if ctx.in_db("Item", tpl):
            if not frappe.db.get_value("Item", tpl, "has_variants"):
                raise SeedError(f"'{tpl}' không phải template (has_variants = 0)")
            other = [n for n in _variant_with_value(tpl, attr, val) if n != code]
            if other:
                raise SeedError(f"'{tpl}' đã có biến thể {attr}={val} với mã khác: {other}")

        if ctx.apply:
            from erpnext.controllers.item_variant import create_variant

            doc = create_variant(tpl, {attr: val})
            doc.item_code = code
            doc.item_name = r["item_name"]
            doc.insert()
            if doc.name != code:
                raise SeedError(f"ERPNext đặt mã biến thể '{doc.name}', khác '{code}'")
        ctx.plan("Item", code)
        rep.add("created", code, f"{tpl} / {attr}={val} / {r['item_name']}")
