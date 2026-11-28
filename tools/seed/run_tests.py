"""Chạy test của tools/seed bằng python của bench (mỗi test một hàm loader, dữ liệu ZZTEST-, tự dọn trong finally).

    cd ~/frappe-bench/sites
    ../env/bin/python "<repo>/tools/seed/run_tests.py" --site local.com [--tests t_uom,t_price]

Cuối cùng in số bản ghi ZZTEST- còn sót (phải là {}). Mã thoát 1 khi có test FAIL hoặc còn sót.
"""
import sys
import traceback
from pathlib import Path

TESTS = ("t_rename", "t_uom", "t_item_group", "t_item_variant", "t_price")


def _cli(argv=None):
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--site", required=True)
    ap.add_argument("--tests", default=",".join(TESTS))
    ap.add_argument("--sites-path")
    a = ap.parse_args(argv)

    here = Path(__file__).resolve().parent
    sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != here]
    sys.path.insert(0, str(here.parent))
    import importlib

    from seed.run import frappe_session

    names = [t.strip() for t in a.tests.split(",") if t.strip()]
    unknown = [t for t in names if t not in TESTS]
    if unknown:
        print(f"Test không tồn tại: {unknown}. Có: {list(TESTS)}")
        return 1
    results = {}
    with frappe_session(a.site, a.sites_path):
        for t in names:
            try:
                importlib.import_module(f"seed.tests.{t}").run()
                results[t] = "PASS"
            except Exception:  # noqa: BLE001
                traceback.print_exc()
                results[t] = "FAIL"
        from seed.tests._util import leftovers

        left = leftovers()
    print("\n### KẾT QUẢ TEST")
    for t, r in results.items():
        print(f"  {t:<16} {r}")
    print(f"  ZZTEST- còn sót: {left}")
    return 0 if all(r == "PASS" for r in results.values()) and not left else 1


if __name__ == "__main__":
    sys.exit(_cli())
