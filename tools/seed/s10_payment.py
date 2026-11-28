"""Bước 10: tài khoản ngân hàng dev + gắn vào Mode of Payment chuyển khoản (Q10); kiểm tra tiền mặt, Cost Center."""
import frappe

from seed import config
from seed.common import SeedError

TITLE = "Mode of Payment / tài khoản ngân hàng / Cost Center"


def _bank_group(ctx):
    groups = frappe.get_all("Account", filters={"company": ctx.company, "is_group": 1, "account_type": "Bank"},
                            pluck="name")
    if len(groups) != 1:
        raise SeedError(f"Cần đúng 1 nhóm tài khoản Bank của '{ctx.company}', tìm thấy {len(groups)}: {groups}")
    return groups[0]


def _mop_account(mop, company):
    return frappe.db.get_value("Mode of Payment Account",
                               {"parent": mop, "parenttype": "Mode of Payment", "company": company},
                               ["name", "default_account"], as_dict=True)


def load(ctx, rep, rows=None):
    # 1) Tài khoản ngân hàng
    acc = f"{config.BANK_ACCOUNT_NAME} - {ctx.abbr}"
    cur = frappe.db.get_value("Account", acc, ["company", "is_group", "account_type"], as_dict=True)
    if not cur:
        parent = _bank_group(ctx)
        if ctx.apply:
            doc = frappe.get_doc({"doctype": "Account", "account_name": config.BANK_ACCOUNT_NAME,
                                  "parent_account": parent, "company": ctx.company, "account_type": "Bank",
                                  "is_group": 0, "account_currency": ctx.currency}).insert()
            if doc.name != acc:
                raise SeedError(f"ERPNext đặt tên tài khoản '{doc.name}', khác '{acc}'")
        ctx.plan("Account", acc)
        rep.add("created", f"Account {acc}", f"cha '{parent}', type Bank")
    elif cur.company != ctx.company or cur.is_group or cur.account_type != "Bank":
        raise SeedError(f"Account '{acc}' đã có nhưng không phải tài khoản lá Bank của '{ctx.company}'")
    else:
        rep.add("skipped", f"Account {acc}")

    # 2) Gắn vào Mode of Payment chuyển khoản
    mop = config.BANK_MODE_OF_PAYMENT
    info = frappe.db.get_value("Mode of Payment", mop, ["type", "enabled"], as_dict=True)
    if not info:
        raise SeedError(f"Chưa có Mode of Payment '{mop}'")
    if info.type != "Bank":
        raise SeedError(f"Mode of Payment '{mop}' có type '{info.type}', cần 'Bank'")
    row = _mop_account(mop, ctx.company)
    key = f"Mode of Payment {mop}"
    if row and row.default_account == acc and info.enabled:
        rep.add("skipped", key, f"đã gắn {acc}")
    elif row and row.default_account and row.default_account != acc:
        rep.add("skipped", key, f"giữ tài khoản đang gắn '{row.default_account}' (không ghi đè)")
    else:
        if ctx.apply:
            doc = frappe.get_doc("Mode of Payment", mop)
            doc.enabled = 1
            line = next((a for a in doc.accounts if a.company == ctx.company), None)
            if line:
                line.default_account = acc
            else:
                doc.append("accounts", {"company": ctx.company, "default_account": acc})
            doc.save()
        rep.add("updated", key, f"gắn {acc} cho {ctx.company}")

    # 3) Kiểm tra: tiền mặt có tài khoản, Company có Cost Center
    cash = [m for m in frappe.get_all("Mode of Payment", filters={"type": "Cash", "enabled": 1}, pluck="name")
            if (_mop_account(m, ctx.company) or {}).get("default_account")]
    if not cash:
        raise SeedError(f"Không có Mode of Payment tiền mặt nào có tài khoản cho '{ctx.company}'")
    rep.add("skipped", "Mode of Payment tiền mặt", ", ".join(cash))
    if not ctx.cost_center:
        raise SeedError(f"Company '{ctx.company}' chưa có Cost Center mặc định")
    rep.add("skipped", "Cost Center", ctx.cost_center)
