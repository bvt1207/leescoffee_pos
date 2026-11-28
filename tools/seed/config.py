"""Cấu hình nạp dữ liệu demo (quyết định Van 2026-11-28, Q1-Q12).

Không chứa tên Company / abbr: các loader đọc từ site (common.Ctx).
File này không import frappe (clean.py dùng chung).
"""

# --- Chi nhánh / kho (Q2) ---------------------------------------------------
BRANCH_KEYS = ("A", "B", "C")
BRANCHES = {
    "A": "Chi nhánh LC Nguyễn Huệ",
    "B": "Chi nhánh LC Lê Lợi",
    "C": "Chi nhánh LC Thủ Đức",
}
# Tên kho KHÔNG kèm hậu tố; ERPNext tự thêm " - <abbr>" của Company trên site.
WAREHOUSES = {
    "A": "Kho LC Nguyễn Huệ",
    "B": "Kho LC Lê Lợi",
    "C": "Kho LC Thủ Đức",
}
WAREHOUSE_GROUP = "Hệ thống Cửa hàng"

# Hậu tố công ty trong file nguồn (vd " - LCV", " - LC") bị bỏ trước khi đối chiếu.
SOURCE_SUFFIX_RE = r"\s+-\s+[A-Za-z]{1,8}$"
# Tên kho trong file nguồn (đã bỏ hậu tố) -> khóa chi nhánh.
SOURCE_WAREHOUSE_KEY = {
    "Kho Cửa hàng Nguyễn Huệ": "A",
    "Kho Cửa hàng Lê Lợi": "B",
    "Kho Cửa hàng Quận 7": "C",  # Quận 7 đổi thành Thủ Đức
    "Kho Chi nhánh A": "A",
    "Kho Chi nhánh B": "B",
    "Kho Chi nhánh C": "C",
}

# --- UOM (Q3): ưu tiên dạng đã có trên site ----------------------------------
# khóa viết thường -> tên UOM dùng trên site
UOM_MAP = {
    "lít": "Litre",
    "ml": "Millilitre",
    "gram": "Gram",
    "kg": "Kg",
}
# UOM phải có sẵn trên site (không tạo, không sửa).
SITE_UOMS = ("Litre", "Millilitre", "Gram", "Kg")
# UOM Item đang dùng nhưng sheet UOM thiếu -> tạo mới: {tên: must_be_whole_number}
EXTRA_UOMS = {"Chai": 1}
# Quy đổi đơn vị nhỏ -> đơn vị lớn (chỉ dùng cho stock_mapping.csv)
UOM_FACTOR = {"Gram": ("Kg", 1000), "Millilitre": ("Litre", 1000)}

# --- Size (Q4 = Item Variant, Q5 = dùng lại Medium / Large có sẵn) ------------
SIZE_ATTRIBUTE = "Size"
SIZE_VALUE_MAP = {
    "size m": "Medium",
    "m": "Medium",
    "medium": "Medium",
    "size l": "Large",
    "l": "Large",
    "large": "Large",
}
SIZE_ABBR = {"Medium": "M", "Large": "L"}  # mã biến thể = <mã template>-<abbr>

# --- Sheet nguồn ------------------------------------------------------------
XLSX_FILE = "Data.xlsx"
OPENING_CSV_FILE = "LC_TON_DAU_KY_ERPNext_V16.csv"  # chỉ xuất stock_mapping.csv, KHÔNG nạp (Q6)

SHEET_UOM = "UOM"
SHEET_ITEM_GROUP = "Item group"
SHEET_WAREHOUSE = "Warehouse"
SHEET_ITEM = "Item (Sản phẩm)"
SHEET_VARIANT = "Variant"
SHEET_SELLING = "Selling price"
SHEET_BUYING = "Buying price"
SHEET_CUSTOMER = "Customer"
OPENING_STOCK_SHEET = "Stock entry (lần 1 - test POS)"  # Q6 = (ii), nhân cho 3 kho

# Chỉ dùng để cảnh báo giá mâu thuẫn, không nạp.
PRICE_CONFLICT_SHEETS = (
    "Bản sao của Selling price",
    "Selling price kh có size",
    "Bản sao của Buying price",
)

# --- Thanh toán (Q10) -------------------------------------------------------
BANK_ACCOUNT_NAME = "Ngân hàng"  # tài khoản dev tạm, Van đổi sau
BANK_MODE_OF_PAYMENT = "Wire Transfer"
