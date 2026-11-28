"""Hỗ trợ test loader: dữ liệu tạm tiền tố ZZTEST-, dọn trong finally (thử lại khi deadlock)."""
import time

import frappe

from seed.common import Ctx, Report


def ctx(mode="apply"):
    return Ctx(mode)


def run_load(mod, rows, mode="apply"):
    c = ctx(mode)
    rep = Report(mod.__name__.rsplit(".", 1)[-1], mod.TITLE, mode)
    mod.load(c, rep, rows)
    if mode == "apply":
        frappe.db.commit()
    return rep.counts


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def _is_deadlock(e):
    qd = getattr(frappe, "QueryDeadlockError", None) or getattr(frappe.exceptions, "QueryDeadlockError", None)
    return (qd is not None and isinstance(e, qd)) or "deadlock" in str(e).lower()


def cleanup(*targets, retries=4):
    """targets: (doctype, name) theo thứ tự xóa (con trước cha). Thử lại khi deadlock."""
    for attempt in range(retries):
        try:
            for doctype, name in targets:
                if frappe.db.exists(doctype, name):
                    frappe.delete_doc(doctype, name, force=1, ignore_permissions=True)
            frappe.db.commit()
            return
        except Exception as e:
            frappe.db.rollback()
            if _is_deadlock(e) and attempt < retries - 1:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise


def leftovers(prefix="ZZTEST-"):
    out = {}
    for dt, field in (("UOM", "name"), ("Item Group", "name"), ("Item", "name"), ("Item Price", "item_code")):
        n = frappe.db.count(dt, {field: ("like", f"{prefix}%")})
        if n:
            out[dt] = n
    return out
