"""Bước 3: Branch (field `company` là Custom Field của mypos, gán Company của site)."""
import frappe

from seed.common import SeedError, read_csv

TITLE = "Branch"


def load(ctx, rep, rows=None):
    rows = read_csv("branch.csv") if rows is None else rows
    has_company = frappe.get_meta("Branch").has_field("company")
    if not has_company:
        rep.warn("Branch chưa có field `company` (chưa migrate mypos?) -> không gán Company")
    for r in rows:
        name = r["branch"]
        if not frappe.db.exists("Branch", name):
            if ctx.apply:
                doc = {"doctype": "Branch", "branch": name}
                if has_company:
                    doc["company"] = ctx.company
                frappe.get_doc(doc).insert()
            ctx.plan("Branch", name)
            rep.add("created", name, f"company={ctx.company}" if has_company else "")
            continue
        if not has_company:
            rep.add("skipped", name)
            continue
        cur = frappe.db.get_value("Branch", name, "company")
        if cur == ctx.company:
            rep.add("skipped", name)
        elif cur:
            raise SeedError(f"Branch '{name}' đang thuộc Company '{cur}', khác '{ctx.company}'")
        else:
            if ctx.apply:
                doc = frappe.get_doc("Branch", name)
                doc.company = ctx.company
                doc.save()
            rep.add("updated", name, f"company={ctx.company}")
