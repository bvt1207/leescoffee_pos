"""Test s01_uom.load: tạo / chạy lại bỏ qua / sửa cờ / UOM dạng site thiếu -> lỗi."""
import frappe

from seed import s01_uom
from seed.common import SeedError
from seed.tests._util import check, cleanup, run_load

NAME = "ZZTEST-UOM"


def run():
    try:
        cleanup(("UOM", NAME))
        rows = [{"uom": NAME, "symbol": "zz", "must_be_whole_number": "1", "source": "new"}]
        c = run_load(s01_uom, rows, "dry-run")
        check(c["created"] == 1 and not frappe.db.exists("UOM", NAME), f"dry-run không được ghi: {c}")
        c = run_load(s01_uom, rows)
        check(c["created"] == 1 and frappe.db.exists("UOM", NAME), f"lần 1 phải tạo: {c}")
        c = run_load(s01_uom, rows)
        check(c["skipped"] == 1 and c["created"] == 0, f"lần 2 phải bỏ qua: {c}")
        rows[0]["must_be_whole_number"] = "0"
        c = run_load(s01_uom, rows)
        check(c["updated"] == 1, f"đổi cờ phải cập nhật: {c}")
        try:
            run_load(s01_uom, [{"uom": "ZZTEST-UOM-KHONG-CO", "must_be_whole_number": "0", "source": "site"}])
            raise AssertionError("UOM dạng site thiếu phải báo lỗi")
        except SeedError:
            frappe.db.rollback()
        print("PASS t_uom")
        return "PASS"
    finally:
        cleanup(("UOM", NAME))
