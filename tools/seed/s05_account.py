"""Bước 5: tài khoản theo chi nhánh (Cash / Stock / Bank / Sales / COGS / Write Off) theo sheet Account.

Cha là nhóm tài khoản có sẵn của Company (vd 'Cash In Hand - <abbr>'); không tạo nhóm mới.
"""
import frappe

from seed.common import SeedError, read_csv

TITLE = "Account"


def load(ctx, rep, rows=None):
    rows = read_csv("account.csv") if rows is None else rows
    for r in rows:
        full = ctx.full(r["account_name"])
        parent = ctx.full(r["parent_account"])
        p = frappe.db.get_value("Account", parent, ["company", "is_group", "root_type"], as_dict=True)
        if not p or p.company != ctx.company or not p.is_group:
            raise SeedError(f"Account '{full}': nhóm cha '{parent}' không có / không phải nhóm của '{ctx.company}'")
        if r.get("root_type") and p.root_type != r["root_type"]:
            raise SeedError(f"Account '{full}': file ghi Root Type {r['root_type']}, nhóm cha là {p.root_type}")
        currency = r.get("currency") or ctx.currency
        cur = frappe.db.get_value("Account", full, ["company", "is_group", "parent_account", "account_type",
                                                    "account_currency", "disabled"], as_dict=True)
        if not cur:
            if ctx.apply:
                doc = frappe.get_doc({"doctype": "Account", "account_name": r["account_name"], "company": ctx.company,
                                      "parent_account": parent, "is_group": 0,
                                      "account_type": r["account_type"] or None,
                                      "account_currency": currency}).insert()
                if doc.name != full:
                    raise SeedError(f"ERPNext đặt tên '{doc.name}', khác dự kiến '{full}'")
            ctx.plan("Account", full)
            rep.add("created", full, f"cha '{parent}', loại '{r['account_type'] or '-'}'")
            continue
        if cur.company != ctx.company or cur.is_group:
            raise SeedError(f"Account '{full}' đã có nhưng khác Company hoặc là nhóm")
        if (cur.account_currency or currency) != currency:
            raise SeedError(f"Account '{full}' có tiền tệ {cur.account_currency}, file ghi {currency}")
        diff = {}
        if cur.parent_account != parent:
            diff["parent_account"] = parent
        if (cur.account_type or "") != r["account_type"]:
            diff["account_type"] = r["account_type"] or None
        if cur.disabled:
            diff["disabled"] = 0
        if not diff:
            rep.add("skipped", full)
            continue
        if ctx.apply:
            doc = frappe.get_doc("Account", full)
            doc.update(diff)
            doc.save()
        rep.add("updated", full, ", ".join(f"{k}={v}" for k, v in diff.items()))
