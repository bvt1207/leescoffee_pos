"""Chạy các bước nạp dữ liệu theo thứ tự phụ thuộc. Mặc định dry-run (không ghi site).

Chạy ĐỘC LẬP bằng python của bench (không dùng `bench execute`: Frappe coi phần đầu đường dẫn là tên app):

    cd ~/frappe-bench/sites
    ../env/bin/python "<repo>/tools/seed/run.py" --site local.com --mode dry-run [--with-demo-customers] [--with-suppliers]

--mode:
  dry-run  so sánh với site, in sẽ tạo / sửa / bỏ qua; không ghi gì (rollback ở cuối cho chắc).
  trial    ghi thật để ERPNext chạy validate (bắt lỗi dữ liệu thật), rồi ROLLBACK toàn bộ — kể cả khi lỗi giữa chừng
           hoặc Ctrl+C; mọi lệnh commit bị chặn. Stock Reconciliation chỉ insert (validate), không submit.
           Sau trial chạy `bench --site <site> clear-cache` (từ ~/frappe-bench).
  apply    ghi và commit sau MỖI bước thành công; lỗi -> rollback bước đó và dừng (các bước trước giữ nguyên).
--stage 1 (mặc định: dữ liệu nền s01-s16) | 2 (Giai đoạn 2: s17 thu ngân thử, s18 POS Profile, s19 MYPOS Menu) | all.
Tham số khác: --until <bước>, --only <bước,bước>, --company (khi site có > 1 Company), --sites-path
(mặc định: thư mục hiện tại nếu có <site>/, không thì ~/frappe-bench/sites). Dừng ở lỗi đầu tiên; mã thoát 1 khi lỗi.
"""
import importlib
import os
import sys
import traceback
from contextlib import contextmanager
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
    "s15_demo_customer",  # chỉ khi --with-demo-customers
    "s16_supplier",  # chỉ khi --with-suppliers
    # Giai đoạn 2 (--stage 2): thu ngân thử, POS Profile, MYPOS Menu
    "s17_cashier_user",
    "s18_pos_profile",
    "s19_mypos_menu",
)
OPTIONAL = {"s15_demo_customer": "with_demo_customers", "s16_supplier": "with_suppliers"}
STAGE2 = ("s17_cashier_user", "s18_pos_profile", "s19_mypos_menu")


def _truthy(v):
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def _select(only=None, until=None, flags=None, stage="1"):
    flags = flags or {}
    if str(stage) not in ("1", "2", "all"):
        raise ValueError(f"--stage phải là 1, 2 hoặc all, nhận '{stage}'")
    steps = [s for s in STEPS if s not in OPTIONAL or _truthy(flags.get(OPTIONAL[s]))]
    if str(stage) == "1":
        steps = [s for s in steps if s not in STAGE2]
    elif str(stage) == "2":
        steps = [s for s in steps if s in STAGE2]
    if only:
        wanted = [s.strip() for s in (only.split(",") if isinstance(only, str) else only) if s.strip()]
        unknown = [s for s in wanted if s not in STEPS]
        if unknown:
            raise ValueError(f"Bước không tồn tại: {unknown}. Có: {list(STEPS)}")
        steps = [s for s in steps if s in wanted]
    if until:
        if until not in STEPS:
            raise ValueError(f"--until '{until}' không tồn tại. Có: {list(STEPS)}")
        steps = [s for s in steps if STEPS.index(s) <= STEPS.index(until)]
    return steps


class _CommitBlocked(Exception):
    pass


def main(mode="dry-run", only=None, until=None, company=None, with_demo_customers=0, with_suppliers=0, stage="1"):
    """Chạy các bước trong một phiên frappe ĐÃ kết nối (xem frappe_session)."""
    import frappe

    from seed.common import Ctx, Report, SeedError

    steps = _select(only, until, {"with_demo_customers": with_demo_customers, "with_suppliers": with_suppliers}, stage)
    ctx = Ctx(mode, company)
    print(f"\n### seed {mode.upper()} | site {frappe.local.site} | user {frappe.session.user} | Company "
          f"'{ctx.company}' (abbr {ctx.abbr}, {ctx.currency}) | {len(steps)} bước: {', '.join(steps)}")
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
            frappe.db.rollback()  # trial / dry-run: bỏ mọi thứ chưa commit, kể cả khi KeyboardInterrupt
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


# --- chạy độc lập ---------------------------------------------------------------------------------

def fix_sys_path():
    """Bỏ tools/seed khỏi sys.path (tránh common.py / config.py che module khác), thêm tools/ để import `seed`."""
    here = Path(__file__).resolve().parent
    sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != here]
    if str(here.parent) not in sys.path:
        sys.path.insert(0, str(here.parent))


def resolve_sites_path(site, sites_path=None):
    candidates = [Path(sites_path).expanduser()] if sites_path else [
        Path.cwd(), Path.home() / "frappe-bench" / "sites"]
    for c in candidates:
        if (c / site / "site_config.json").is_file():
            return str(c.resolve())
    raise SystemExit(f"Không tìm thấy {site}/site_config.json trong {[str(c) for c in candidates]}. "
                     "Chạy từ ~/frappe-bench/sites hoặc truyền --sites-path.")


@contextmanager
def frappe_session(site, sites_path=None):
    """frappe.init + connect + Administrator; cuối: rollback phần chưa commit rồi destroy (luôn chạy)."""
    import frappe

    frappe.init(site=site, sites_path=resolve_sites_path(site, sites_path))
    try:
        frappe.connect()
        frappe.set_user("Administrator")
        frappe.flags.mute_emails = True  # không gửi email khi tạo Contact / Customer mẫu
        yield frappe
    finally:
        try:
            if getattr(frappe.local, "db", None):
                frappe.db.rollback()
        finally:
            frappe.destroy()


def _cli(argv=None):
    import argparse

    ap = argparse.ArgumentParser(description="Nạp dữ liệu demo vào site (chạy bằng python của bench)")
    ap.add_argument("--site", required=True)
    ap.add_argument("--mode", default="dry-run", choices=("dry-run", "trial", "apply"))
    ap.add_argument("--until", choices=STEPS)
    ap.add_argument("--only", help="danh sách bước, phân cách dấu phẩy")
    ap.add_argument("--company")
    ap.add_argument("--with-demo-customers", action="store_true")
    ap.add_argument("--with-suppliers", action="store_true")
    ap.add_argument("--stage", default="1", choices=("1", "2", "all"),
                    help="1 = dữ liệu nền s01-s16 (mặc định); 2 = thu ngân thử + POS Profile + MYPOS Menu (s17-s19)")
    ap.add_argument("--sites-path")
    a = ap.parse_args(argv)

    fix_sys_path()
    from seed.common import SeedError

    try:
        with frappe_session(a.site, a.sites_path):
            res = main(a.mode, a.only, a.until, a.company, int(a.with_demo_customers), int(a.with_suppliers),
                       a.stage)
    except (SeedError, ValueError) as e:
        print(f"### LỖI: {e}")
        return 1
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(_cli())
