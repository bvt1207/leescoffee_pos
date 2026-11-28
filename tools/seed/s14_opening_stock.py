"""Bước 14: tồn đầu kỳ = Stock Reconciliation purpose "Opening Stock", 1 chứng từ / kho chi nhánh.

Nguồn: clean/opening_stock.csv (từ LC_TON_DAU_KY_ERPNext_V16.csv). Tài khoản chênh lệch = tài khoản
account_type Temporary của Company; Cost Center = của chi nhánh; ngày ghi sổ = ngày apply.
Kho đã có Stock Reconciliation Opening Stock đã submit -> bỏ qua cả kho.
"""
from collections import OrderedDict

import frappe
from frappe.utils import nowdate, nowtime

from seed.common import SeedError, read_csv, require, to_float

TITLE = "Tồn đầu kỳ (Stock Reconciliation - Opening Stock)"


def _temporary_account(ctx):
    accs = frappe.get_all("Account", filters={"company": ctx.company, "account_type": "Temporary",
                                              "is_group": 0, "disabled": 0}, pluck="name")
    if len(accs) != 1:
        raise SeedError(f"Cần đúng 1 tài khoản Temporary của '{ctx.company}', tìm thấy {len(accs)}: {accs}")
    return accs[0]


def _opening_docs(ctx, wh):
    return frappe.db.sql(
        """select distinct sr.name, sr.docstatus from `tabStock Reconciliation` sr
           join `tabStock Reconciliation Item` sri on sri.parent = sr.name
           where sr.purpose = 'Opening Stock' and sr.company = %s and sri.warehouse = %s and sr.docstatus < 2""",
        (ctx.company, wh), as_dict=True)


def _by_key(fname, name_field, flt=None):
    return {r["key"]: r[name_field] for r in read_csv(fname) if r["key"] and (flt is None or flt(r))}


def load(ctx, rep, rows=None):
    rows = read_csv("opening_stock.csv") if rows is None else rows
    warehouses = _by_key("warehouse.csv", "warehouse_name", lambda r: r["is_group"] in ("0", 0, ""))
    cost_centers = _by_key("cost_center.csv", "cost_center_name")
    account = _temporary_account(ctx)
    posting_date = nowdate()
    from erpnext.accounts.utils import get_fiscal_year

    try:
        get_fiscal_year(posting_date, company=ctx.company)
    except Exception as e:
        raise SeedError(f"Ngày {posting_date} không nằm trong Fiscal Year nào của '{ctx.company}': {e}")

    groups = OrderedDict()
    for r in rows:
        groups.setdefault(r["warehouse_key"], []).append(r)

    for key, lines in groups.items():
        if key not in warehouses or key not in cost_centers:
            raise SeedError(f"Khóa chi nhánh '{key}' không có trong warehouse.csv / cost_center.csv")
        wh, cc = ctx.full(warehouses[key]), ctx.full(cost_centers[key])
        require(ctx, "Warehouse", wh, "Tồn đầu kỳ")
        require(ctx, "Cost Center", cc, "Tồn đầu kỳ")

        if ctx.in_db("Warehouse", wh):
            docs = _opening_docs(ctx, wh)
            done = [d.name for d in docs if d.docstatus == 1]
            drafts = [d.name for d in docs if d.docstatus == 0]
            if done:
                rep.add("skipped", wh, f"đã có {', '.join(done)}")
                continue
            if drafts:
                raise SeedError(f"{wh}: có Stock Reconciliation nháp {drafts}; xóa hoặc submit tay rồi chạy lại")
            if frappe.db.exists("Stock Ledger Entry", {"warehouse": wh, "is_cancelled": 0}):
                raise SeedError(f"{wh}: kho đã có giao dịch kho, không nạp tồn đầu kỳ chồng lên")

        items = []
        for ln in lines:
            code = ln["item_code"]
            require(ctx, "Item", code, f"Tồn đầu kỳ {wh}")
            if ctx.in_db("Item", code):
                it = frappe.db.get_value("Item", code, ["is_stock_item", "has_variants", "disabled", "stock_uom"],
                                         as_dict=True)
                if not it.is_stock_item or it.has_variants or it.disabled:
                    raise SeedError(f"{wh}: '{code}' không quản lý kho / là template / đang tắt")
                if ln.get("uom") and ln["uom"] != it.stock_uom:
                    raise SeedError(f"{wh}: '{code}' UOM '{ln['uom']}' khác UOM của Item '{it.stock_uom}'")
            items.append({"item_code": code, "warehouse": wh, "qty": to_float(ln["qty"]),
                          "valuation_rate": to_float(ln["valuation_rate"])})
        total = sum(i["qty"] * i["valuation_rate"] for i in items)
        detail = f"{len(items)} mã, giá trị {total:,.0f}, TK chênh lệch {account}, Cost Center {cc}, ngày {posting_date}"
        if ctx.apply:
            doc = frappe.get_doc({
                "doctype": "Stock Reconciliation", "company": ctx.company, "purpose": "Opening Stock",
                "set_posting_time": 1, "posting_date": posting_date, "posting_time": nowtime(),
                "expense_account": account, "cost_center": cc, "set_warehouse": wh, "items": items,
            })
            doc.insert()
            if not ctx.trial:  # trial: chỉ validate (insert), không submit / không ghi sổ kho
                doc.submit()
            detail = f"{doc.name}: {detail}"
        rep.add("created", wh, detail)
