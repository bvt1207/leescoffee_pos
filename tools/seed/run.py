"""Chạy các bước nạp dữ liệu theo thứ tự phụ thuộc. Mặc định dry-run (không ghi site).

Cách 1 (bench execute, cần PYTHONPATH trỏ tới thư mục tools/):
    PYTHONPATH="<repo>/tools" bench --site <site> execute seed.run.main --kwargs "{'mode': 'dry-run'}"
Cách 2 (dự phòng, tự frappe.init):
    cd ~/frappe-bench/sites && ../env/bin/python "<repo>/tools/seed/run.py" --site <site> --mode dry-run

mode:
  dry-run  so sánh với site, in sẽ tạo / sửa / bỏ qua; không ghi gì.
  trial    ghi thật để ERPNext chạy validate (bắt lỗi dữ liệu thật), rồi ROLLBACK toàn bộ; mọi lệnh commit bị chặn.
           Stock Reconciliation chỉ insert (validate), không submit. Sau trial nên chạy `bench --site <site> clear-cache`.
  apply    ghi và commit sau mỗi bước thành công.
Tham số khác: only = "s01_uom,s02_item_group"; until = "s07_mode_of_payment"; company (khi site có > 1 Company);
with_demo_customers = 1 (bước s15); with_suppliers = 1 (bước s16). Dừng ở lỗi đầu tiên.
"""
import importlib
import sys
import traceback
from pathlib import Path

STEPS = (
    "s01_uom",
    "s02_item_group",
    "s03_branch",
    "s04_cost_center",
    "s05_account",
    "s06_warehouse",
    "s07_mode_of_payment",
    "s08_attribute",
    "s09_item",
    "s10_variant",
    "s11_price_list",
    "s12_item_price",
    "s13_customer",
    "s14_opening_stock",
    "s15_demo_customer",  # chỉ khi with_demo_customers
    "s16_supplier",  # chỉ khi with_suppliers
)
OPTIONAL = {"s15_demo_customer": "with_demo_customers", "s16_supplier": "with_suppliers"}


def _truthy(v):
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def _select(only=None, until=None, flags=None):
    flags = flags or {}
    steps = [s for s in STEPS if s not in OPTIONAL or _truthy(flags.get(OPTIONAL[s]))]
    if only:
        wanted = [s.strip() for s in (only.split(",") if isinstance(only, str) else only) if s.strip()]
        unknown = [s for s in wanted if s not in STEPS]
        if unknown:
            raise ValueError(f"Bước không tồn tại: {unknown}. Có: {list(STEPS)}")
        steps = [s for s in steps if s in wanted]
    if until:
        if until not in STEPS:
            raise ValueError(f"until='{until}' không tồn tại. Có: {list(STEPS)}")
        steps = [s for s in steps if STEPS.index(s) <= STEPS.index(until)]
    return steps


class _CommitBlocked(Exception):
    pass


def main(mode="dry-run", only=None, until=None, company=None, with_demo_customers=0, with_suppliers=0):
    import frappe

    from seed.common import Ctx, Report, SeedError

    steps = _select(only, until, {"with_demo_customers": with_demo_customers, "with_suppliers": with_suppliers})
    ctx = Ctx(mode, company)
    print(f"\n### seed {mode.upper()} | site {frappe.local.site} | Company '{ctx.company}' (abbr {ctx.abbr}, "
          f"{ctx.currency}) | {len(steps)} bước: {', '.join(steps)}")
    if mode == "dry-run":
        print("### DRY-RUN: không ghi gì. 'sẽ created/updated' = việc apply sẽ làm (chưa qua validate của ERPNext).")
    elif mode == "trial":
        print("### TRIAL: ghi tạm để ERPNext validate, ROLLBACK toàn bộ ở cuối; commit bị chặn.")

    real_commit = frappe.db.commit
    if ctx.trial:
        def _blocked(*a, **k):
            raise _CommitBlocked("trial: có lệnh commit ngầm -> dừng để không ghi thật")
        frappe.db.commit = _blocked

    reports, failed = [], None
    try:
        for name in steps:
            mod = importlib.import_module(f"seed.{name}")
            rep = Report(name, mod.TITLE, mode)
            reports.append(rep)
            print(f"\n== {name}: {mod.TITLE}")
            try:
                mod.load(ctx, rep)
                if mode == "apply":
                    frappe.db.commit()
            except Exception as e:  # dừng ở lỗi đầu tiên
                if mode == "apply":
                    frappe.db.rollback()
                rep.counts["error"] += 1
                print(f"  [error] {e}")
                if not isinstance(e, SeedError):
                    traceback.print_exc()
                failed = name
                break
    finally:
        if mode != "apply":
            frappe.db.rollback()
        frappe.db.commit = real_commit

    print(f"\n### TỔNG KẾT ({mode})")
    for rep in reports:
        print("  " + rep.line())
    if failed:
        tail = {"apply": "Các bước trước đó đã commit.", "trial": "Đã rollback toàn bộ.", "dry-run": "Không ghi gì."}
        print(f"### DỪNG ở bước {failed}. {tail[mode]}")
    else:
        print("### XONG." + (" Đã rollback toàn bộ (trial)." if mode == "trial" else ""))
    return {"ok": not failed, "failed_step": failed, "mode": mode}


def _cli(argv=None):
    import argparse

    ap = argparse.ArgumentParser(description="Nạp dữ liệu demo (dự phòng khi không dùng bench execute)")
    ap.add_argument("--site", required=True)
    ap.add_argument("--mode", default="dry-run", choices=("dry-run", "trial", "apply"))
    ap.add_argument("--only")
    ap.add_argument("--until")
    ap.add_argument("--company")
    ap.add_argument("--with-demo-customers", action="store_true")
    ap.add_argument("--with-suppliers", action="store_true")
    ap.add_argument("--sites-path", default=".")
    a = ap.parse_args(argv)

    here = Path(__file__).resolve().parent
    # Chạy dạng script: bỏ tools/seed khỏi sys.path (tránh common.py / config.py che module khác), thêm tools/
    sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != here]
    sys.path.insert(0, str(here.parent))
    import frappe

    frappe.init(site=a.site, sites_path=a.sites_path)
    frappe.connect()
    try:
        res = main(a.mode, a.only, a.until, a.company, int(a.with_demo_customers), int(a.with_suppliers))
    finally:
        frappe.destroy()
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(_cli())
