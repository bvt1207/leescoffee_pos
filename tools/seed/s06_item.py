"""Bước 6: Item (món thường + template có biến thể Size)."""
import frappe

from seed.common import SeedError, read_csv, require, to_int

TITLE = "Item (món thường + template)"
FIELDS = ("item_name", "item_group", "stock_uom", "is_stock_item", "has_variants")


def load(ctx, rep, rows=None):
    rows = read_csv("item.csv") if rows is None else rows
    for r in rows:
        code = r["item_code"]
        want = {"item_name": r["item_name"], "item_group": r["item_group"], "stock_uom": r["stock_uom"],
                "is_stock_item": to_int(r["is_stock_item"]), "has_variants": to_int(r["has_variants"])}
        attr = r.get("attribute") or ""
        require(ctx, "Item Group", want["item_group"], f"Item '{code}'")
        require(ctx, "UOM", want["stock_uom"], f"Item '{code}'")
        if want["has_variants"]:
            require(ctx, "Item Attribute", attr, f"Item '{code}'")

        cur = frappe.db.get_value("Item", code, ["variant_of", *FIELDS], as_dict=True)
        if not cur:
            if ctx.apply:
                doc = {"doctype": "Item", "item_code": code, **want}
                if r.get("material_request_type"):
                    doc["default_material_request_type"] = r["material_request_type"]
                if want["has_variants"]:
                    doc["attributes"] = [{"attribute": attr}]
                frappe.get_doc(doc).insert()
            ctx.plan("Item", code)
            rep.add("created", code, want["item_name"] + (" [template]" if want["has_variants"] else ""))
            continue

        if cur.variant_of:
            raise SeedError(f"Item '{code}' đã có trên site nhưng là biến thể của '{cur.variant_of}'")
        diff = {}
        for k, v in want.items():
            have = int(cur.get(k) or 0) if isinstance(v, int) else (cur.get(k) or "")
            if have != v:
                diff[k] = v
        if not diff:
            rep.add("skipped", code)
            continue
        if ctx.apply:
            doc = frappe.get_doc("Item", code)
            doc.update(diff)
            if want["has_variants"] and not any(a.attribute == attr for a in doc.attributes):
                doc.append("attributes", {"attribute": attr})
            doc.save()
        rep.add("updated", code, ", ".join(f"{k}: {cur.get(k)!r} -> {v!r}" for k, v in diff.items()))
