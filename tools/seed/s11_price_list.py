"""Bước 11: Price List bán / mua theo chi nhánh."""
import frappe

from seed.common import SeedError, read_csv, to_int

TITLE = "Price List"
FLAGS = ("buying", "selling", "enabled")


def load(ctx, rep, rows=None):
    rows = read_csv("price_list.csv") if rows is None else rows
    for r in rows:
        name = r["price_list"]
        want = {k: to_int(r[k]) for k in FLAGS}
        if not frappe.db.exists("Currency", r["currency"]):
            raise SeedError(f"Price List '{name}': chưa có Currency '{r['currency']}'")
        cur = frappe.db.get_value("Price List", name, ["currency", *FLAGS], as_dict=True)
        if not cur:
            if ctx.apply:
                frappe.get_doc({"doctype": "Price List", "price_list_name": name, "currency": r["currency"],
                                **want}).insert()
            ctx.plan("Price List", name)
            rep.add("created", name, f"{r['currency']}, " + ", ".join(f"{k}={v}" for k, v in want.items()))
            continue
        if cur.currency != r["currency"]:
            raise SeedError(f"Price List '{name}' có tiền tệ {cur.currency}, file ghi {r['currency']}")
        diff = {k: v for k, v in want.items() if int(cur.get(k) or 0) != v}
        if not diff:
            rep.add("skipped", name)
            continue
        if ctx.apply:
            doc = frappe.get_doc("Price List", name)
            doc.update(diff)
            doc.save()
        rep.add("updated", name, ", ".join(f"{k}={v}" for k, v in diff.items()))
