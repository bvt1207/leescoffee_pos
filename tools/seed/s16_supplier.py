"""Bước 16 (chỉ chạy khi run.py --with-suppliers): Supplier Group + Supplier theo file."""
import frappe

from seed.common import SeedError, read_csv, require, to_int

TITLE = "Nhà cung cấp (with_suppliers)"
FIELDS = ("supplier_type", "supplier_group", "country", "default_currency")


def _groups(ctx, rep, rows):
    for r in rows:
        name, parent, is_group = r["supplier_group"], r["parent_supplier_group"], to_int(r["is_group"])
        require(ctx, "Supplier Group", parent, f"Supplier Group '{name}'")
        cur = frappe.db.get_value("Supplier Group", name, ["parent_supplier_group", "is_group"], as_dict=True)
        if not cur:
            if ctx.apply:
                frappe.get_doc({"doctype": "Supplier Group", "supplier_group_name": name,
                                "parent_supplier_group": parent, "is_group": is_group}).insert()
            ctx.plan("Supplier Group", name)
            rep.add("created", f"Supplier Group {name}")
        elif cur.parent_supplier_group != parent or int(cur.is_group or 0) != is_group:
            if ctx.apply:
                doc = frappe.get_doc("Supplier Group", name)
                doc.parent_supplier_group, doc.is_group = parent, is_group
                doc.save()
            rep.add("updated", f"Supplier Group {name}")
        else:
            rep.add("skipped", f"Supplier Group {name}")


def _suppliers(ctx, rep, rows):
    for r in rows:
        nm = r["supplier_name"]
        require(ctx, "Supplier Group", r["supplier_group"], f"Supplier '{nm}'")
        if r.get("country"):
            require(ctx, "Country", r["country"], f"Supplier '{nm}'")
        want = {k: r[k] for k in FIELDS if r.get(k)}
        want["disabled"] = to_int(r.get("disabled"))
        found = frappe.get_all("Supplier", filters={"supplier_name": nm}, fields=["name", "disabled", *FIELDS])
        if len(found) > 1:
            raise SeedError(f"Có {len(found)} Supplier tên '{nm}'")
        if not found:
            if ctx.apply:
                frappe.get_doc({"doctype": "Supplier", "supplier_name": nm, **want}).insert()
            rep.add("created", f"Supplier {nm}", f"nhóm {r['supplier_group']}")
            continue
        cur = found[0]
        diff = {k: v for k, v in want.items() if (int(cur.get(k) or 0) if k == "disabled" else (cur.get(k) or "")) != v}
        if not diff:
            rep.add("skipped", f"Supplier {cur.name}")
            continue
        if ctx.apply:
            doc = frappe.get_doc("Supplier", cur.name)
            doc.update(diff)
            doc.save()
        rep.add("updated", f"Supplier {cur.name}", ", ".join(diff))


def load(ctx, rep, rows=None):
    _groups(ctx, rep, read_csv("supplier_group.csv") if rows is None else rows.get("groups", []))
    _suppliers(ctx, rep, read_csv("supplier.csv") if rows is None else rows.get("suppliers", []))
