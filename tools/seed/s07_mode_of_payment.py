"""Bước 7: 6 Mode of Payment — mỗi chi nhánh "Cash - Chi nhánh LC ..." (Cash) + "QR Bank Transfer - Chi nhánh LC ..."
(Bank), mỗi cái gắn 1 tài khoản của Company.

ERPNext bắt buộc tài khoản lá loại Bank / Cash / Receivable cùng Company (mode_of_payment.validate_accounts).
Tài khoản lấy từ sheet Account (bước 5); không tự tạo tài khoản khác. Dòng tài khoản đang gắn tài khoản khác
cho cùng Company -> không ghi đè, dừng để Van quyết.
"""
import frappe

from seed.common import SeedError, read_csv, require, to_int

TITLE = "Mode of Payment"


def load(ctx, rep, rows=None):
    rows = read_csv("mode_of_payment.csv") if rows is None else rows
    for r in rows:
        name, mtype, enabled = r["mode_of_payment"], r["type"], to_int(r["enabled"])
        account = ctx.full(r["account"])
        require(ctx, "Account", account, f"Mode of Payment '{name}'")
        if ctx.in_db("Account", account):
            a = frappe.db.get_value("Account", account, ["company", "is_group", "account_type"], as_dict=True)
            if a.company != ctx.company or a.is_group or a.account_type not in ("Bank", "Cash", "Receivable"):
                raise SeedError(f"Mode of Payment '{name}': tài khoản '{account}' phải là tài khoản lá loại "
                                f"Bank / Cash / Receivable của '{ctx.company}' (đang: {a.account_type})")

        cur = frappe.db.get_value("Mode of Payment", name, ["type", "enabled"], as_dict=True)
        if not cur:
            if ctx.apply:
                frappe.get_doc({"doctype": "Mode of Payment", "mode_of_payment": name, "type": mtype,
                                "enabled": enabled,
                                "accounts": [{"company": ctx.company, "default_account": account}]}).insert()
            ctx.plan("Mode of Payment", name)
            rep.add("created", name, f"type {mtype}, tài khoản {account}")
            continue

        line = frappe.db.get_value("Mode of Payment Account",
                                   {"parent": name, "parenttype": "Mode of Payment", "company": ctx.company},
                                   "default_account")
        if line and line != account:
            raise SeedError(f"Mode of Payment '{name}' đang gắn '{line}' cho '{ctx.company}', file ghi '{account}' "
                            "(không ghi đè; sửa tay trên Desk nếu muốn đổi)")
        diff = {}
        if cur.type != mtype:
            diff["type"] = mtype
        if int(cur.enabled or 0) != enabled:
            diff["enabled"] = enabled
        if not diff and line == account:
            rep.add("skipped", name)
            continue
        if ctx.apply:
            doc = frappe.get_doc("Mode of Payment", name)
            doc.update(diff)
            if not line:
                doc.append("accounts", {"company": ctx.company, "default_account": account})
            doc.save()
        rep.add("updated", name, ", ".join([f"{k}={v}" for k, v in diff.items()] +
                                           ([] if line else [f"gắn {account}"])))
