"""Bước 6: kho. Kho nhóm mỗi chi nhánh dưới kho gốc của Company; kho con gắn tài khoản Stock riêng (Q2)."""
import frappe

from seed.common import SeedError, read_csv, require, to_int

TITLE = "Warehouse"


def load(ctx, rep, rows=None):
    rows = read_csv("warehouse.csv") if rows is None else rows
    root = ctx.root("Warehouse", "parent_warehouse")
    for r in rows:
        full = ctx.full(r["warehouse_name"])
        parent = ctx.full(r["parent"]) if r["parent"] else root
        is_group = to_int(r["is_group"])
        account = ctx.full(r["account"]) if r.get("account") else ""
        require(ctx, "Warehouse", parent, f"Kho '{full}'")
        if account:
            require(ctx, "Account", account, f"Kho '{full}'")
        want = {"parent_warehouse": parent, "is_group": is_group}
        if account:
            want["account"] = account
        cur = frappe.db.get_value("Warehouse", full, ["company", "is_group", "parent_warehouse", "account",
                                                      "disabled"], as_dict=True)
        if not cur:
            if ctx.apply:
                doc = frappe.get_doc({"doctype": "Warehouse", "warehouse_name": r["warehouse_name"],
                                      "company": ctx.company, **want}).insert()
                if doc.name != full:
                    raise SeedError(f"ERPNext đặt tên kho '{doc.name}', khác dự kiến '{full}'")
            ctx.plan("Warehouse", full)
            rep.add("created", full, ", ".join(f"{k}={v}" for k, v in want.items()))
            continue
        if cur.company != ctx.company:
            raise SeedError(f"Kho '{full}' thuộc Company '{cur.company}'")
        diff = {k: v for k, v in want.items() if (int(cur.get(k) or 0) if k == "is_group" else cur.get(k)) != v}
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
