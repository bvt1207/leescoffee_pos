"""Test s08_price.load: tạo giá bán, chạy lại bỏ qua, đổi giá -> cập nhật (không tạo dòng thứ 2)."""
import frappe

from seed import s08_price
from seed.tests._util import check, cleanup, run_load

GROUP, ITEM = "ZZTEST-IG-PRICE", "ZZTEST-PRICE-ITEM"


def _price_list():
    pl = frappe.db.get_single_value("Selling Settings", "selling_price_list")
    return pl or frappe.get_all("Price List", filters={"selling": 1, "enabled": 1}, pluck="name", limit=1)[0]


def _targets():
    prices = [("Item Price", n) for n in frappe.get_all("Item Price", filters={"item_code": ITEM}, pluck="name")]
    return (*prices, ("Item", ITEM), ("Item Group", GROUP))


def run():
    try:
        cleanup(*_targets())
        root = frappe.db.sql("select name from `tabItem Group` where ifnull(parent_item_group, '') = '' limit 1",
                             pluck=True)[0]
        frappe.get_doc({"doctype": "Item Group", "item_group_name": GROUP, "parent_item_group": root,
                        "is_group": 0}).insert()
        frappe.get_doc({"doctype": "Item", "item_code": ITEM, "item_name": "ZZTEST Price", "item_group": GROUP,
                        "stock_uom": "Nos", "is_stock_item": 0}).insert()
        frappe.db.commit()
        pl = _price_list()
        cur = frappe.db.get_value("Price List", pl, "currency")
        rows = [{"item_code": ITEM, "price_list": pl, "rate": "12345", "currency": cur, "kind": "selling"}]
        c = run_load(s08_price, rows)
        check(c["created"] == 1, f"lần 1: {c}")
        c = run_load(s08_price, rows)
        check(c["skipped"] == 1 and c["created"] == 0, f"lần 2: {c}")
        rows[0]["rate"] = "23456"
        c = run_load(s08_price, rows)
        check(c["updated"] == 1, f"đổi giá: {c}")
        got = frappe.get_all("Item Price", filters={"item_code": ITEM, "price_list": pl}, pluck="price_list_rate")
        check(got == [23456], f"phải còn đúng 1 dòng giá 23456: {got}")
        print("PASS t_price")
        return "PASS"
    finally:
        cleanup(*_targets())
