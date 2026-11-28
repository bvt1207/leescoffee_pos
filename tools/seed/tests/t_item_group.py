"""Test s02_item_group.load: cha + con, dry-run nhận cha 'sẽ tạo', chạy lại bỏ qua."""
import frappe

from seed import s02_item_group
from seed.tests._util import check, cleanup, run_load

PARENT, CHILD = "ZZTEST-IG-CHA", "ZZTEST-IG-CON"


def _root():
    return frappe.db.sql("select name from `tabItem Group` where ifnull(parent_item_group, '') = '' limit 1",
                         pluck=True)[0]


def run():
    try:
        cleanup(("Item Group", CHILD), ("Item Group", PARENT))
        rows = [{"item_group": PARENT, "parent_item_group": _root(), "is_group": "1"},
                {"item_group": CHILD, "parent_item_group": PARENT, "is_group": "0"}]
        c = run_load(s02_item_group, rows, "dry-run")
        check(c["created"] == 2 and not frappe.db.exists("Item Group", PARENT), f"dry-run: {c}")
        c = run_load(s02_item_group, rows)
        check(c["created"] == 2, f"lần 1: {c}")
        check(frappe.db.get_value("Item Group", CHILD, "parent_item_group") == PARENT, "sai nhóm cha")
        c = run_load(s02_item_group, rows)
        check(c["skipped"] == 2 and c["created"] == 0, f"lần 2: {c}")
        print("PASS t_item_group")
        return "PASS"
    finally:
        cleanup(("Item Group", CHILD), ("Item Group", PARENT))
