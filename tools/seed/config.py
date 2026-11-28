"""Cấu hình nạp dữ liệu demo từ "Data_Test.xlsx" / "Data Test.xlsx" (quyết định Van 2026-11-28, bản chốt cuối).

Không chứa tên Company / abbr: loader đọc từ site (common.Ctx). Không import frappe (clean.py dùng chung).
"""

# --- Đổi tên chi nhánh (Q5): một quy tắc cho mọi nơi ---------------------------
# "Chi nhánh A" -> "Chi nhánh LC Nguyễn Huệ" (giữ nguyên hoa / thường của "Chi"),
# áp cho Branch, Cost Center, Account, Mode of Payment, Price List, Warehouse, CSV tồn đầu kỳ.
BRANCH_KEYS = ("A", "B", "C")
BRANCH_LABEL = {
    "A": "LC Nguyễn Huệ",
    "B": "LC Lê Lợi",
    "C": "LC Thủ Đức",
}
BRANCH_TOKEN_RE = r"(?i)\b(chi nhánh)\s+([ABC])(?=$|[\s\-])"

# Hậu tố công ty trong file nguồn (vd " - LC") bị bỏ; loader thêm " - <abbr của site>".
SOURCE_SUFFIX_RE = r"\s+-\s+[A-Za-z]{1,8}$"

# --- File / sheet nguồn ---------------------------------------------------------
# Tên file chấp nhận (đúng 1 file tồn tại; có cả 2 -> dừng). Data.xlsx cũ bị bỏ qua.
XLSX_FILES = ("Data_Test.xlsx", "Data Test.xlsx")
OPENING_CSV_FILE = "LC_TON_DAU_KY_ERPNext_V16.csv"  # nguồn tồn đầu kỳ (khớp sheet Item)

SHEET_COMPANY = "Company (Ko cần import)"  # chỉ đọc tên Company trong file để nhận diện cột cha
SHEET_BRANCH = "Branch"
SHEET_COST_CENTER = "Cost center"
SHEET_ACCOUNT = "Account"
SHEET_MODE_OF_PAYMENT = "Mode of payment"
SHEET_WAREHOUSES = ("Warehouse (lần 1)", "Warehouse (lần 2)")
SHEET_UOM = "UOM"
SHEET_ITEM_GROUPS = ("Item group (lần 1)", "Item group (lần 2)", "Item group (lần 3)")
SHEET_ITEM = "Item"
SHEET_VARIANT = "Item - Các biến thể"
SHEET_PRICE_LIST = "Price list"
SHEET_SELLING = "Item price - giá bán"
SHEET_BUYING = "Item price - giá mua NVL"
SHEET_CUSTOMER_GROUP = "Customer group"
SHEET_CUSTOMER = "Customer"
SHEET_PRODUCT_BUNDLE = "Product Bundle"  # bước riêng, làm sau khi POS chạy; clean chỉ xuất CSV
SHEET_SUPPLIER_GROUP = "Supplier group"  # chỉ nạp khi with_suppliers
SHEET_SUPPLIER = "Supplier"

# Gốc cây trên site (cột cha trong file trỏ tới các gốc này -> loader tự tìm gốc của Company).
ROOT_WAREHOUSE_BASE = "All Warehouses"
ROOT_ITEM_GROUP = "All Item Groups"
ROOT_CUSTOMER_GROUP = "All Customer Groups"
ROOT_SUPPLIER_GROUP = "All Supplier Groups"

# --- UOM: ưu tiên dạng có sẵn trên site -----------------------------------------
UOM_MAP = {"lít": "Litre", "ml": "Millilitre", "gram": "Gram", "kg": "Kg"}  # khóa viết thường
SITE_UOMS = ("Litre", "Millilitre", "Gram", "Kg")  # phải có sẵn, không sửa

# --- Size (Q1): dùng lại Small / Medium / Large có sẵn ---------------------------
SIZE_ATTRIBUTE = "Size"
SIZE_ABBR = {"Small": "S", "Medium": "M", "Large": "L"}  # mã biến thể = <template>-<abbr>

# --- Khách vãng lai (Q8) -------------------------------------------------------
WALK_IN_CUSTOMER_GROUP = "Khách lẻ"
WALK_IN_TERRITORY = "Vietnam"

# --- Thanh toán (quyết định 6) ----------------------------------------------------
# Ngoài Cash / Transfer của file, mỗi chi nhánh thêm 1 Mode of Payment loại Bank, cùng tài khoản Bank của chi nhánh.
# Tên = "<EXTRA_BANK_MODE_LABEL> - Chi nhánh LC ..." (lấy phần chi nhánh từ Mode of Payment Bank của file).
EXTRA_BANK_MODE_LABEL = "QR Bank Transfer"

# --- Khách mẫu (cờ with_demo_customers) --------------------------------------------
DEMO_EMAIL_DOMAIN = "example.com"  # chỉ nạp khách có email đúng tên miền này

# --- Ghi chú định mức (chỉ cảnh báo) ------------------------------------------------
ICE_ITEM = "NL-008"
