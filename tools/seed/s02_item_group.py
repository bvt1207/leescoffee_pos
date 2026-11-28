"""Bước 2: Item Group (cha trước con, theo thứ tự clean/item_group.csv)."""
import frappe

from seed.common import read_csv, require, to_int

TITLE = "Item Group"


def load(ctx, rep, rows=None):
    rows = read_csv("item_group.csv") if rows is None else rows
    for r in rows:
        name, parent, is_group = r["item_group"], r["parent_item_group"], to_int(r["is_group"])
        require(ctx, "Item Group", parent, f"Item Group '{name}'")
        cur = frappe.db.get_value("Item Group", name, ["parent_item_group", "is_group"], as_dict=True)
        if not cur:
            if ctx.apply:
                frappe.get_doc({"doctype": "Item Group", "item_group_name": name,
                                "parent_item_group": parent, "is_group": is_group}).insert()
            ctx.plan("Item Group", name)
            rep.add("created", name, f"cha '{parent}', is_group={is_group}")
            continue
        diff = {}
        if cur.parent_item_group != parent:
            diff["parent_item_group"] = parent
        if int(cur.is_group or 0) != is_group:
            diff["is_group"] = is_group
        if not diff:
            rep.add("skipped", name)
            continue
        if ctx.apply:
            doc = frappe.get_doc("Item Group", name)
            doc.update(diff)
            doc.save()
        rep.add("updated", name, ", ".join(f"{k}={v}" for k, v in diff.items()))
