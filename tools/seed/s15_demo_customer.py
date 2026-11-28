"""Bước 15 (chỉ chạy khi run.py --with-demo-customers): khách mẫu trong sheet Customer (email @example.com) + Contact.

clean.py đã chặn khách có email khác tên miền mẫu. Territory giữ như file. Contact khóa theo email.
"""
import frappe

from seed import config
from seed.common import SeedError, read_csv, require, to_int

TITLE = "Khách mẫu (with_demo_customers)"
FIELDS = ("customer_type", "customer_group", "territory")


def _contact_for(email):
    return frappe.db.get_value("Contact Email", {"email_id": email, "parenttype": "Contact"}, "parent")


def _linked(contact, customer):
    return frappe.db.exists("Dynamic Link", {"parenttype": "Contact", "parent": contact,
                                             "link_doctype": "Customer", "link_name": customer})


def _customer(ctx, rep, r):
    nm = r["customer_name"]
    found = frappe.get_all("Customer", filters={"customer_name": nm}, fields=["name", *FIELDS])
    if len(found) > 1:
        raise SeedError(f"Có {len(found)} Customer tên '{nm}'")
    if not found:
        if ctx.apply:
            doc = frappe.get_doc({"doctype": "Customer", "customer_name": nm, **{k: r[k] for k in FIELDS}}).insert()
            return doc.name, "created"
        return None, "created"
    cur = found[0]
    diff = {k: r[k] for k in FIELDS if (cur.get(k) or "") != r[k]}
    if diff and ctx.apply:
        doc = frappe.get_doc("Customer", cur.name)
        doc.update(diff)
        doc.save()
    return cur.name, ("updated" if diff else "skipped")


def _contact(ctx, r, customer):
    email = r["email"]
    contact = _contact_for(email)
    if contact and customer and _linked(contact, customer):
        return "skipped"
    if not ctx.apply:
        return "updated" if contact else "created"
    if contact:
        doc = frappe.get_doc("Contact", contact)
        doc.append("links", {"link_doctype": "Customer", "link_name": customer})
        doc.save()
        return "updated"
    doc = {"doctype": "Contact", "first_name": r["first_name"] or r["customer_name"], "last_name": r["last_name"],
           "designation": r.get("designation") or "", "is_primary_contact": to_int(r.get("is_primary_contact")),
           "email_ids": [{"email_id": email, "is_primary": 1}],
           "links": [{"link_doctype": "Customer", "link_name": customer}]}
    phones = [{"phone": r[k], f"is_primary_{k}": 1} for k in ("phone", "mobile_no") if r.get(k)]
    if phones:
        doc["phone_nos"] = phones
    frappe.get_doc(doc).insert()
    return "created"


def load(ctx, rep, rows=None):
    rows = read_csv("demo_customer.csv") if rows is None else rows
    for r in rows:
        if not r["email"].endswith("@" + config.DEMO_EMAIL_DOMAIN):
            raise SeedError(f"'{r['customer_name']}': email không phải @{config.DEMO_EMAIL_DOMAIN}, không nạp")
        require(ctx, "Customer Group", r["customer_group"], f"Customer '{r['customer_name']}'")
        require(ctx, "Territory", r["territory"], f"Customer '{r['customer_name']}'")
        name, action = _customer(ctx, rep, r)
        rep.add(action, f"Customer {r['customer_name']}", ", ".join(f"{k}={r[k]}" for k in FIELDS))
        c_action = _contact(ctx, r, name)
        rep.add(c_action, f"Contact {r['email']}", f"liên kết Customer {name or r['customer_name']}")
