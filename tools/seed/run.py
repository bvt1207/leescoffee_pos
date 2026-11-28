"""Chạy các bước nạp dữ liệu theo thứ tự phụ thuộc. Mặc định dry-run (không ghi site).

Cách 1 (bench execute, cần PYTHONPATH trỏ tới thư mục tools/):
    PYTHONPATH="<repo>/tools" bench --site <site> execute seed.run.main --kwargs "{'mode': 'dry-run'}"
Cách 2 (dự phòng, tự frappe.init):
    cd ~/frappe-bench/sites && ../env/bin/python "<repo>/tools/seed/run.py" --site <site> --mode dry-run

Tham số: mode = dry-run | apply; only = "s01_uom,s02_item_group"; until = "s10_payment"; company = tên Company
(chỉ cần khi site có hơn 1 Company). Dừng ở lỗi đầu tiên; apply commit sau mỗi bước thành công.
"""
import importlib
import sys
import traceback
from pathlib import Path

STEPS = (
    "s01_uom",
    "s02_item_group",
    "s03_branch",
    "s04_warehouse",
    "s05_attribute",
    "s06_item",
    "s07_variant",
    "s08_price",
    "s09_customer",
    "s10_payment",
    "s11_opening_stock",
)


def _select(only=None, until=None):
    steps = list(STEPS)
    if only:
        wanted = [s.strip() for s in (only.split(",") if isinstance(only, str) else only) if s.strip()]
        unknown = [s for s in wanted if s not in STEPS]
        if unknown:
            raise ValueError(f"Bước không tồn tại: {unknown}. Có: {list(STEPS)}")
        steps = [s for s in STEPS if s in wanted]
    if until:
        if until not in STEPS:
            raise ValueError(f"until='{until}' không tồn tại. Có: {list(STEPS)}")
        steps = [s for s in steps if STEPS.index(s) <= STEPS.index(until)]
    return steps


def main(mode="dry-run", only=None, until=None, company=None):
    import frappe

    from seed.common import Ctx, Report, SeedError

    steps = _select(only, until)
    ctx = Ctx(mode, company)
    print(f"\n### seed {mode.upper()} | site {frappe.local.site} | Company '{ctx.company}' (abbr {ctx.abbr}, "
          f"{ctx.currency}) | {len(steps)} bước")
    if not ctx.apply:
        print("### DRY-RUN: không ghi gì vào site. 'sẽ created/updated' = việc apply sẽ làm.")

    reports, failed = [], None
    for name in steps:
        mod = importlib.import_module(f"seed.{name}")
        rep = Report(name, mod.TITLE, mode)
        reports.append(rep)
        print(f"\n== {name}: {mod.TITLE}")
        try:
            mod.load(ctx, rep)
            if ctx.apply:
                frappe.db.commit()
        except Exception as e:  # dừng ở lỗi đầu tiên
            frappe.db.rollback()
            rep.counts["error"] += 1
            print(f"  [error] {e}")
            if not isinstance(e, SeedError):
                traceback.print_exc()
            failed = name
            break
    if not ctx.apply:
        frappe.db.rollback()

    print("\n### TỔNG KẾT" + (" (dry-run)" if not ctx.apply else ""))
    for rep in reports:
        print("  " + rep.line())
    if failed:
        print(f"### DỪNG ở bước {failed}. Bước trước đó " + ("đã commit." if ctx.apply else "không ghi gì."))
    else:
        print("### XONG.")
    return {"ok": not failed, "failed_step": failed, "mode": mode}


def _cli(argv=None):
    import argparse

    ap = argparse.ArgumentParser(description="Nạp dữ liệu demo (dự phòng khi không dùng bench execute)")
    ap.add_argument("--site", required=True)
    ap.add_argument("--mode", default="dry-run", choices=("dry-run", "apply"))
    ap.add_argument("--only")
    ap.add_argument("--until")
    ap.add_argument("--company")
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
        res = main(a.mode, a.only, a.until, a.company)
        if a.mode == "apply":
            frappe.db.commit()
    finally:
        frappe.destroy()
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(_cli())
