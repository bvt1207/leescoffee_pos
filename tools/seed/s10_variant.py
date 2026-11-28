"""Bước 10: biến thể Size (mã <template>-S / -M / -L, tên / mô tả / ảnh / cờ bán-mua theo sheet).

Ảnh: URL riêng ở cột Image của dòng biến thể. Dòng trống -> không ghi (create_variant chỉ chép ảnh template khi
use_template_image; script không bật), báo trong log."""
import frappe

from seed.common import SeedError, read_csv, require, to_int

TITLE = "Item Variant"
INT_FIELDS = ("is_sales_item", "is_purchase_item", "disabled")


def _variant_with_value(template, attribute, value):
    return frappe.db.sql(
        """select v.name from `tabItem` v
           join `tabItem Variant Attribute` a on a.parent = v.name and a.parenttype = 'Item'
           where v.variant_of = %s and a.attribute = %s and a.attribute_value = %s""",
        (template, attribute, value), pluck=True)


def _want(r):
    want = {"item_name": r["item_name"]}
    for k in ("description", "image"):
        if r.get(k):
            want[k] = r[k]
    want.update({k: to_int(r[k]) for k in INT_FIELDS if k in r})
    return want


def load(ctx, rep, rows=None):
    rows = read_csv("variant.csv") if rows is None else rows
    for r in rows:
        code, tpl, attr, val = r["item_code"], r["variant_of"], r["attribute"], r["attribute_value"]
        want = _want(r)
        require(ctx, "Item", tpl, f"Biến thể '{code}'")

        if not r.get("image"):
            rep.warn(f"Biến thể '{code}' không có ảnh trong file (không tự lấy ảnh template)")
        cur = frappe.db.get_value("Item", code, ["variant_of", "item_name", "description", "image", *INT_FIELDS],
                                  as_dict=True)
        if cur:
            if cur.variant_of != tpl:
                raise SeedError(f"Item '{code}' đã có nhưng variant_of = '{cur.variant_of}', cần '{tpl}'")
            have = frappe.db.get_value("Item Variant Attribute", {"parent": code, "parenttype": "Item",
                                                                  "attribute": attr}, "attribute_value")
            if have != val:
                raise SeedError(f"Biến thể '{code}' có {attr} = '{have}', cần '{val}' (không tự sửa)")
            diff = {k: v for k, v in want.items()
                    if (int(cur.get(k) or 0) if isinstance(v, int) else (cur.get(k) or "")) != v}
            if not diff:
                rep.add("skipped", code)
                continue
            if ctx.apply:
                doc = frappe.get_doc("Item", code)
                doc.update(diff)
                doc.save()
            rep.add("updated", code, ", ".join(diff))
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
            doc.update(want)
            doc.insert()
            if doc.name != code:
                raise SeedError(f"ERPNext đặt mã biến thể '{doc.name}', khác '{code}'")
        ctx.plan("Item", code)
        rep.add("created", code, f"{tpl} / {attr}={val} / {r['item_name']}")
