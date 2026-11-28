"""Bước 19 (Giai đoạn 2): MYPOS Menu mỗi chi nhánh (theo Price List bán của chi nhánh), 10 món theo config.MENU_ITEMS.

Món có size = template (POS tự lấy biến thể S/M/L). Thứ tự dòng = thứ tự tab nhóm trên /pos. Menu đã có mà khác danh
sách / thứ tự / Price List -> cập nhật cho khớp.
"""
import frappe

from seed import config
from seed.branches import branch_setup
from seed.common import SeedError, read_csv, require

TITLE = "MYPOS Menu"


def _check_items(rep):
    items = {r["item_code"]: r for r in read_csv("item.csv")}
    for code in config.MENU_ITEMS:
        it = items.get(code)
        if not it:
            raise SeedError(f"Món menu '{code}' không có trong clean/item.csv")
        if str(it["is_sales_item"]) != "1":
            raise SeedError(f"Món menu '{code}' có is_sales_item = 0")


def load(ctx, rep, rows=None):
    _check_items(rep)
    want_items = list(config.MENU_ITEMS)
    for k, b in branch_setup(ctx).items():
        name, pl = b["menu"], b["price_list"]
        require(ctx, "Price List", pl, f"Menu '{name}'")
        for code in want_items:
            require(ctx, "Item", code, f"Menu '{name}'")
        other = frappe.get_all("MYPOS Menu", filters={"price_list": pl, "name": ("!=", name)}, pluck="name")
        if other:
            rep.warn(f"Price List '{pl}' đã có menu khác {other}: /pos sẽ hiện món của tất cả menu cùng Price List")

        if not frappe.db.exists("MYPOS Menu", name):
            if ctx.apply:
                frappe.get_doc({"doctype": "MYPOS Menu", "menu_name": name, "price_list": pl,
                                "items": [{"item_code": c} for c in want_items]}).insert()
            ctx.plan("MYPOS Menu", name)
            rep.add("created", name, f"Price List {pl}, {len(want_items)} món: {', '.join(want_items)}")
            continue
        doc = frappe.get_doc("MYPOS Menu", name)
        have = [r.item_code for r in doc.items]
        diff = []
        if doc.price_list != pl:
            diff.append(f"price_list {doc.price_list} -> {pl}")
        if have != want_items:
            diff.append(f"món {have} -> {want_items}")
        if not diff:
            rep.add("skipped", name)
            continue
        if ctx.apply:
            doc.price_list = pl
            doc.set("items", [])
            for c in want_items:
                doc.append("items", {"item_code": c})
            doc.save()
        rep.add("updated", name, "; ".join(diff))
