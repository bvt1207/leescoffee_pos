"""Bước 17 (Giai đoạn 2): 3 user thu ngân thử (@example.com, role POS CASHIER), mỗi chi nhánh 1 user.

Không đặt mật khẩu, không gửi email chào mừng: Van tự đặt mật khẩu trên Desk (User -> Change Password).
User đã có: chỉ bật lại + thêm role thiếu, không đổi tên / mật khẩu.
"""
import frappe

from seed import config
from seed.branches import branch_setup
from seed.common import SeedError

TITLE = "User thu ngân thử"


def load(ctx, rep, rows=None):
    if not frappe.db.exists("Role", config.CASHIER_ROLE):
        raise SeedError(f"Chưa có Role '{config.CASHIER_ROLE}' (app mypos chưa cài / chưa migrate?)")
    for k, b in branch_setup(ctx).items():
        email = b["cashier"]
        if not email.endswith("@example.com"):
            raise SeedError(f"User thử phải là @example.com: {email}")
        cur = frappe.db.get_value("User", email, ["enabled", "user_type"], as_dict=True)
        if not cur:
            if ctx.apply:
                frappe.get_doc({"doctype": "User", "email": email, "first_name": "Thu ngân",
                                "last_name": b["branch"].replace("Chi nhánh ", ""), "user_type": "System User",
                                "enabled": 1, "send_welcome_email": 0,
                                "roles": [{"role": config.CASHIER_ROLE}]}).insert()
            ctx.plan("User", email)
            rep.add("created", email, f"role {config.CASHIER_ROLE}, chi nhánh {b['branch']} (chưa có mật khẩu)")
            continue
        has_role = frappe.db.exists("Has Role", {"parent": email, "parenttype": "User", "role": config.CASHIER_ROLE})
        diff = []
        if not cur.enabled:
            diff.append("enabled=1")
        if cur.user_type != "System User":
            diff.append("user_type=System User")
        if not has_role:
            diff.append(f"thêm role {config.CASHIER_ROLE}")
        if not diff:
            rep.add("skipped", email)
            continue
        if ctx.apply:
            doc = frappe.get_doc("User", email)
            doc.enabled, doc.user_type = 1, "System User"
            if not has_role:
                doc.append("roles", {"role": config.CASHIER_ROLE})
            doc.save()
        rep.add("updated", email, ", ".join(diff))
