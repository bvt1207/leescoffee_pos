"""Bước 9: Customer khách vãng lai (không SĐT, không Loyalty Program — điều kiện của POS Profile)."""
import frappe

from seed.common import SeedError, read_csv, require

TITLE = "Customer (khách vãng lai)"
FIELDS = ("customer_type", "customer_group", "territory")


def load(ctx, rep, rows=None):
    rows = read_csv("customer.csv") if rows is None else rows
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
                frappe.get_doc({"doctype": "Customer", "customer_name": nm,
                                **{k: r[k] for k in FIELDS}}).insert()
            rep.add("created", nm, ", ".join(f"{k}={r[k]}" for k in FIELDS))
            continue
        cur = found[0]
        if cur.loyalty_program:
            raise SeedError(f"Customer '{cur.name}' có Loyalty Program; khách vãng lai không được tích điểm")
        diff = {k: r[k] for k in FIELDS if (cur.get(k) or "") != r[k]}
        if cur.disabled:
            diff["disabled"] = 0
        if not diff:
            rep.add("skipped", cur.name)
            continue
        if ctx.apply:
            doc = frappe.get_doc("Customer", cur.name)
            doc.update(diff)
            doc.save()
        rep.add("updated", cur.name, ", ".join(f"{k}={v}" for k, v in diff.items()))
