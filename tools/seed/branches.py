"""Gom tài nguyên theo chi nhánh (khóa A/B/C) từ clean/*.csv cho Giai đoạn 2 (POS Profile, Menu)."""
from seed import config
from seed.common import SeedError, read_csv


def branch_setup(ctx):
    branch = {r["key"]: r["branch"] for r in read_csv("branch.csv")}
    warehouse = {r["key"]: r["warehouse_name"] for r in read_csv("warehouse.csv")
                 if r["key"] and str(r["is_group"]) == "0"}
    cost_center = {r["key"]: r["cost_center_name"] for r in read_csv("cost_center.csv")}
    selling_pl = {r["key"]: r["price_list"] for r in read_csv("price_list.csv") if str(r["selling"]) == "1"}
    accounts = {}
    for r in read_csv("account.csv"):
        kind = r["account_type"] or r["account_name"].split(" - ")[0]  # Write Off không có account_type
        accounts.setdefault(r["key"], {})[kind] = r["account_name"]
    modes = {}
    for r in read_csv("mode_of_payment.csv"):
        modes.setdefault(r["key"], {})[r["type"]] = r["mode_of_payment"]

    out = {}
    for k in config.BRANCH_KEYS:
        a, m = accounts.get(k, {}), modes.get(k, {})
        need = {"Branch": branch.get(k), "Warehouse": warehouse.get(k), "Cost Center": cost_center.get(k),
                "Price List bán": selling_pl.get(k), "TK Cash": a.get("Cash"), "TK Sales": a.get("Income Account"),
                "TK COGS": a.get("Cost of Goods Sold"), "TK Write Off": a.get("Write Off"),
                "Mode Cash": m.get("Cash"), "Mode Bank": m.get("Bank")}
        missing = [n for n, v in need.items() if not v]
        if missing:
            raise SeedError(f"Chi nhánh {k}: thiếu {missing} trong clean/*.csv (chạy lại clean.py)")
        out[k] = {
            "branch": branch[k],
            "warehouse": ctx.full(warehouse[k]),
            "cost_center": ctx.full(cost_center[k]),
            "price_list": selling_pl[k],
            "cash_account": ctx.full(a["Cash"]),
            "income_account": ctx.full(a["Income Account"]),
            "expense_account": ctx.full(a["Cost of Goods Sold"]),
            "write_off_account": ctx.full(a["Write Off"]),
            "cash_mode": m["Cash"],
            "bank_mode": m["Bank"],
            "cashier": config.TEST_CASHIERS[k],
            "pos_profile": f"{config.POS_PROFILE_PREFIX}{branch[k]}",
            "menu": f"{config.MENU_PREFIX}{branch[k]}",
        }
    return out
