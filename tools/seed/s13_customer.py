"""Bước 13: 3 Customer Group theo file + khách vãng lai (không SĐT, không Loyalty Program, Territory Vietnam — Q8)."""
import frappe

from seed.common import SeedError, read_csv, require, to_int

TITLE = "Customer Group + khách vãng lai"
FIELDS = ("customer_type", "customer_group", "territory")


def _groups(ctx, rep, rows):
    for r in rows:
        name, parent, is_group = r["customer_group"], r["parent_customer_group"], to_int(r["is_group"])
        require(ctx, "Customer Group", parent, f"Customer Group '{name}'")
        cur = frappe.db.get_value("Customer Group", name, ["parent_customer_group", "is_group"], as_dict=True)
        if not cur:
            if ctx.apply:
                frappe.get_doc({"doctype": "Customer Group", "customer_group_name": name,
                                "parent_customer_group": parent, "is_group": is_group}).insert()
            ctx.plan("Customer Group", name)
            rep.add("created", f"Customer Group {name}", f"cha '{parent}'")
        elif cur.parent_customer_group != parent or int(cur.is_group or 0) != is_group:
            if ctx.apply:
                doc = frappe.get_doc("Customer Group", name)
                doc.parent_customer_group, doc.is_group = parent, is_group
                doc.save()
            rep.add("updated", f"Customer Group {name}", f"cha '{parent}', is_group={is_group}")
        else:
            rep.add("skipped", f"Customer Group {name}")


def _customers(ctx, rep, rows):
    for r in rows:
        nm = r["customer_name"]
        require(ctx, "Customer Group", r["customer_group"], f"Customer '{nm}'")
        require(ctx, "Territory", r["territory"], f"Customer '{nm}'")
        found = frappe.get_all("Customer", filters={"customer_name": nm},
                               fields=["name", "disabled", "loyalty_program", *FIELDS])
        if len(found) > 1:
            raise SeedError(f"Có {len(found)} Customer tên '{nm}'")
        if not found:
            if ctx.apply:
                frappe.get_doc({"doctype": "Customer", "customer_name": nm, **{k: r[k] for k in FIELDS}}).insert()
            rep.add("created", f"Customer {nm}", ", ".join(f"{k}={r[k]}" for k in FIELDS))
            continue
        cur = found[0]
        if cur.loyalty_program:
            raise SeedError(f"Customer '{cur.name}' có Loyalty Program; khách vãng lai không được tích điểm")
        diff = {k: r[k] for k in FIELDS if (cur.get(k) or "") != r[k]}
        if cur.disabled:
            diff["disabled"] = 0
        if not diff:
            rep.add("skipped", f"Customer {cur.name}")
            continue
        if ctx.apply:
            doc = frappe.get_doc("Customer", cur.name)
            doc.update(diff)
            doc.save()
        rep.add("updated", f"Customer {cur.name}", ", ".join(f"{k}={v}" for k, v in diff.items()))


def load(ctx, rep, rows=None):
    groups = read_csv("customer_group.csv") if rows is None else rows.get("groups", [])
    customers = read_csv("customer.csv") if rows is None else rows.get("customers", [])
    _groups(ctx, rep, groups)
    _customers(ctx, rep, customers)
