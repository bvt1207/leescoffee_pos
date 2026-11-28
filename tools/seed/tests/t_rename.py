"""Test clean.rename: đổi tên chi nhánh A/B/C idempotent, nhận khóa từ cả tên cũ lẫn tên mới. Không cần frappe.

Chạy: python -c "import sys; sys.path.insert(0, 'tools'); from seed.tests.t_rename import run; run()"
"""
from seed.clean import rename

CASES = [
    ("Chi nhánh A", "Chi nhánh LC Nguyễn Huệ", "A"),
    ("Kho chi nhánh B", "Kho chi nhánh LC Lê Lợi", "B"),
    ("Cash - Chi nhánh C - LC", "Cash - Chi nhánh LC Thủ Đức - LC", "C"),
    ("Giá mua Chi nhánh A", "Giá mua Chi nhánh LC Nguyễn Huệ", "A"),
    ("Chi nhánh LC Nguyễn Huệ", "Chi nhánh LC Nguyễn Huệ", "A"),
    ("QR Bank Transfer - Chi nhánh LC Thủ Đức", "QR Bank Transfer - Chi nhánh LC Thủ Đức", "C"),
    ("Chi nhánh LC", "Chi nhánh LC", ""),
    ("Cà phê sữa", "Cà phê sữa", ""),
]


def run():
    for src, want, key in CASES:
        got, k = rename(src)
        assert (got, k) == (want, key), f"{src!r}: {got!r} / {k!r}, cần {want!r} / {key!r}"
        again, k2 = rename(got)
        assert (again, k2) == (want, key), f"không idempotent: {got!r} -> {again!r}"
        assert "Chi nhánh LC Chi nhánh" not in again and "LC LC" not in again
    print("PASS t_rename")
    return "PASS"
