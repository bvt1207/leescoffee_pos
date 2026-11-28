"""Bước 4: Cost Center mỗi chi nhánh, nằm dưới Cost Center gốc của Company trên site."""
import frappe

from seed.common import SeedError, read_csv, require

TITLE = "Cost Center"


def load(ctx, rep, rows=None):
    rows = read_csv("cost_center.csv") if rows is None else rows
    root = ctx.root("Cost Center", "parent_cost_center")
    for r in rows:
        full = ctx.full(r["cost_center_name"])
        parent = ctx.full(r["parent"]) if r["parent"] else root
        require(ctx, "Cost Center", parent, f"Cost Center '{full}'")
        cur = frappe.db.get_value("Cost Center", full, ["company", "is_group", "parent_cost_center", "disabled"],
                                  as_dict=True)
        if not cur:
            if ctx.apply:
                doc = frappe.get_doc({"doctype": "Cost Center", "cost_center_name": r["cost_center_name"],
                                      "parent_cost_center": parent, "company": ctx.company, "is_group": 0}).insert()
                if doc.name != full:
                    raise SeedError(f"ERPNext đặt tên '{doc.name}', khác dự kiến '{full}'")
            ctx.plan("Cost Center", full)
            rep.add("created", full, f"cha '{parent}'")
            continue
        if cur.company != ctx.company or cur.is_group:
            raise SeedError(f"Cost Center '{full}' đã có nhưng khác Company hoặc là nhóm")
        diff = {}
        if cur.parent_cost_center != parent:
            diff["parent_cost_center"] = parent
        if cur.disabled:
            diff["disabled"] = 0
        if not diff:
            rep.add("skipped", full)
            continue
        if ctx.apply:
            doc = frappe.get_doc("Cost Center", full)
            doc.update(diff)
            doc.save()
        rep.add("updated", full, ", ".join(f"{k}={v}" for k, v in diff.items()))
