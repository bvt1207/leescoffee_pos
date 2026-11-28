"""Bước 18 (Giai đoạn 2): POS Profile mỗi chi nhánh.

Kho, Price List bán, Branch, khách vãng lai, Cost Center, tài khoản Sales / COGS / Write Off / Cash của chi nhánh;
Payments = "Cash - Chi nhánh LC ..." (Default) + "QR Bank Transfer - Chi nhánh LC ..."; Applicable for Users =
thu ngân thử của chi nhánh (Default). Payments / user thêm tay trên Desk được giữ; chỉ bổ sung / sửa 2 mode và 1 user này.
"""
import frappe

from seed.branches import branch_setup
from seed.common import SeedError, read_csv, require

TITLE = "POS Profile"
SCALARS = ("company", "branch", "custom_walk_in_customer", "warehouse", "selling_price_list", "currency",
           "cost_center", "write_off_account", "write_off_cost_center", "income_account", "expense_account",
           "account_for_change_amount", "disabled")


def _walk_in(ctx):
    name = read_csv("customer.csv")[0]["customer_name"]
    found = frappe.get_all("Customer", filters={"customer_name": name}, pluck="name")
    if len(found) != 1:
        raise SeedError(f"Cần đúng 1 Customer '{name}' (khách vãng lai, Giai đoạn 1), tìm thấy {len(found)}")
    return found[0]


def _want(ctx, b, walk_in):
    return {"company": ctx.company, "branch": b["branch"], "custom_walk_in_customer": walk_in,
            "warehouse": b["warehouse"], "selling_price_list": b["price_list"], "currency": ctx.currency,
            "cost_center": b["cost_center"], "write_off_account": b["write_off_account"],
            "write_off_cost_center": b["cost_center"], "income_account": b["income_account"],
            "expense_account": b["expense_account"], "account_for_change_amount": b["cash_account"], "disabled": 0}


def load(ctx, rep, rows=None):
    meta = frappe.get_meta("POS Profile")
    for f in ("branch", "custom_walk_in_customer"):
        if not meta.has_field(f):
            raise SeedError(f"POS Profile chưa có field '{f}' (fixture mypos chưa migrate?)")
    walk_in = _walk_in(ctx)
    for k, b in branch_setup(ctx).items():
        name = b["pos_profile"]
        want = _want(ctx, b, walk_in)
        who = f"POS Profile '{name}'"
        for dt, v in (("Branch", b["branch"]), ("Warehouse", b["warehouse"]), ("Price List", b["price_list"]),
                      ("Cost Center", b["cost_center"]), ("Account", b["write_off_account"]),
                      ("Account", b["income_account"]), ("Account", b["expense_account"]),
                      ("Account", b["cash_account"]), ("Mode of Payment", b["cash_mode"]),
                      ("Mode of Payment", b["bank_mode"]), ("User", b["cashier"])):
            require(ctx, dt, v, who)
        other = frappe.get_all("POS Profile", filters={"branch": b["branch"], "disabled": 0, "name": ("!=", name)},
                               pluck="name")
        if other:
            raise SeedError(f"{who}: Branch '{b['branch']}' đã có POS Profile đang bật {other} (mypos: 1 profile / Branch)")

        if not frappe.db.exists("POS Profile", name):
            if ctx.apply:
                doc = frappe.get_doc({"doctype": "POS Profile", "name": name, "__newname": name, **want,
                                      "payments": [{"mode_of_payment": b["cash_mode"], "default": 1},
                                                   {"mode_of_payment": b["bank_mode"], "default": 0}],
                                      "applicable_for_users": [{"user": b["cashier"], "default": 1}]})
                doc.insert()
                if doc.name != name:
                    raise SeedError(f"ERPNext đặt tên '{doc.name}', khác dự kiến '{name}'")
            ctx.plan("POS Profile", name)
            rep.add("created", name, f"kho {b['warehouse']}, giá {b['price_list']}, thanh toán {b['cash_mode']} "
                                     f"(mặc định) + {b['bank_mode']}, thu ngân {b['cashier']}")
            continue

        doc = frappe.get_doc("POS Profile", name)
        diff = [f for f in SCALARS if (doc.get(f) or (0 if f == "disabled" else "")) != want[f]]
        pays = {p.mode_of_payment: p for p in doc.payments}
        pay_diff = (b["cash_mode"] not in pays or not pays[b["cash_mode"]].default
                    or b["bank_mode"] not in pays or pays[b["bank_mode"]].default
                    or any(p.default for m, p in pays.items() if m != b["cash_mode"]))
        users = {u.user: u for u in doc.applicable_for_users}
        user_diff = b["cashier"] not in users or not users[b["cashier"]].default
        if not diff and not pay_diff and not user_diff:
            rep.add("skipped", name)
            continue
        if ctx.apply:
            doc.update({f: want[f] for f in diff})
            if pay_diff:
                for p in doc.payments:
                    p.default = 1 if p.mode_of_payment == b["cash_mode"] else 0
                for mode, dflt in ((b["cash_mode"], 1), (b["bank_mode"], 0)):
                    if mode not in pays:
                        doc.append("payments", {"mode_of_payment": mode, "default": dflt})
            if user_diff:
                if b["cashier"] in users:
                    users[b["cashier"]].default = 1
                else:
                    doc.append("applicable_for_users", {"user": b["cashier"], "default": 1})
            doc.save()
        rep.add("updated", name, ", ".join(diff + (["payments"] if pay_diff else []) +
                                            (["applicable_for_users"] if user_diff else [])))
