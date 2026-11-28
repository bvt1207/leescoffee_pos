"""Bước 4: Warehouse. Kho nhóm nằm dưới kho gốc của Company; tên = <tên> - <abbr của site>."""
import frappe

from seed.common import SeedError, read_csv, require, to_int

TITLE = "Warehouse"


def _root(ctx):
    roots = frappe.get_all("Warehouse", filters=[["company", "=", ctx.company], ["is_group", "=", 1],
                                                 ["parent_warehouse", "is", "not set"]], pluck="name")
    if len(roots) != 1:
        raise SeedError(f"Cần đúng 1 kho gốc của Company '{ctx.company}', tìm thấy {len(roots)}: {roots}")
    return roots[0]


def load(ctx, rep, rows=None):
    rows = read_csv("warehouse.csv") if rows is None else rows
    root = _root(ctx)
    for r in rows:
        full = ctx.wh(r["warehouse_name"])
        parent = ctx.wh(r["parent"]) if r["parent"] else root
        is_group = to_int(r["is_group"])
        require(ctx, "Warehouse", parent, f"Kho '{full}'")
        cur = frappe.db.get_value("Warehouse", full, ["company", "is_group", "parent_warehouse", "disabled"],
                                  as_dict=True)
        if not cur:
            if ctx.apply:
                doc = frappe.get_doc({"doctype": "Warehouse", "warehouse_name": r["warehouse_name"],
                                      "is_group": is_group, "parent_warehouse": parent, "company": ctx.company})
                doc.insert()
                if doc.name != full:
                    raise SeedError(f"ERPNext đặt tên kho '{doc.name}', khác dự kiến '{full}'")
            ctx.plan("Warehouse", full)
            rep.add("created", full, f"cha '{parent}', is_group={is_group}")
            continue
        if cur.company != ctx.company:
            raise SeedError(f"Kho '{full}' thuộc Company '{cur.company}'")
        diff = {}
        if cur.parent_warehouse != parent:
            diff["parent_warehouse"] = parent
        if int(cur.is_group or 0) != is_group:
            diff["is_group"] = is_group
        if cur.disabled:
            diff["disabled"] = 0
        if not diff:
            rep.add("skipped", full)
            continue
        if ctx.apply:
            doc = frappe.get_doc("Warehouse", full)
            doc.update(diff)
            doc.save()
        rep.add("updated", full, ", ".join(f"{k}={v}" for k, v in diff.items()))
