# tools/seed — nạp dữ liệu demo vào site dev

Không nằm trong app `mypos`. Dữ liệu nguồn `DATA/` ("Data_Test.xlsx" hoặc "Data Test.xlsx" + `LC_TON_DAU_KY_ERPNext_V16.csv`) và dữ liệu sạch
`tools/seed/clean/` không commit (.gitignore). Quyết định: bản chốt cuối 2026-11-28 (mục 1-11), quy tắc ở `config.py`.

Đổi tên chi nhánh ở mọi nơi (Q5): "Chi nhánh A / B / C" -> "Chi nhánh LC Nguyễn Huệ / LC Lê Lợi / LC Thủ Đức".
Company / abbr / gốc cây Cost Center, Warehouse / tài khoản Temporary đọc từ site.

## Thứ tự (Giai đoạn 1 — dữ liệu nền)

| Bước | Việc | Số bản ghi |
|---|---|---|
| `clean.py` | `DATA/` -> `clean/*.csv` + `report.txt` (Python thuần); `--check-urls` thử link ảnh | — |
| s01_uom | UOM mới Cái, Gói, Ly, Chai, Lon (+ Symbol); Litre / Millilitre / Gram chỉ kiểm tra | 5 tạo + 3 kiểm |
| s02_item_group | Cây 3 cấp | 20 |
| s03_branch | Branch, `company` = Company của site | 3 |
| s04_cost_center | Dưới Cost Center gốc của Company | 3 |
| s05_account | Cash / Stock / Bank / Sales / COGS / Write Off mỗi chi nhánh | 18 |
| s06_warehouse | 3 kho nhóm + 3 kho con gắn tài khoản Stock | 6 |
| s07_mode_of_payment | Mỗi chi nhánh: Cash (Cash) + QR Bank Transfer (Bank, tài khoản Bank chi nhánh) | 6 |
| s08_attribute | Chỉ kiểm tra Size Small = S, Medium = M, Large = L | 3 kiểm |
| s09_item | Ảnh = URL ngoài trong file; TP-002 giữ nhóm cha "Đồ uống" | 37 (8 template) |
| s10_variant | `TP-xxx-S/M/L`, ảnh riêng từng dòng | 24 |
| s11_price_list | Giá bán / giá mua mỗi chi nhánh | 6 |
| s12_item_price | | 78 bán + 87 mua |
| s13_customer | 3 Customer Group + "Khách vãng lai" (Territory Vietnam) | 3 + 1 |
| s14_opening_stock | Stock Reconciliation Opening Stock / kho chi nhánh, từ CSV | 3 chứng từ |
| s15_demo_customer | CHỈ khi `with_demo_customers=1`: khách mẫu @example.com + Contact | 14 |
| s16_supplier | CHỈ khi `with_suppliers=1`: Supplier Group + Supplier | 3 + 7 |

File nguồn đã mang tên mới ("Chi nhánh LC ...", "QR Bank Transfer - ..."); `clean.py` vẫn nhận file cũ (A/B/C,
"Transfer - ...") và đổi tên idempotent (`tests/t_rename.py`).

Giai đoạn 2 (sau khi Van duyệt): POS Profile x 3 — Payment Methods mỗi chi nhánh gồm "Cash - Chi nhánh LC ..." (Default)
+ "QR Bank Transfer - Chi nhánh LC ..." của chính chi nhánh; MYPOS Menu. Sửa mypos để Mode of Payment đi theo POS Profile:
để sau. Giai đoạn 3: Product Bundle (`clean/product_bundle.csv`).

## Chế độ chạy

- `dry-run` (mặc định): so với site, không ghi.
- `trial`: ghi tạm để ERPNext validate thật (bắt lỗi như URL ảnh, nhóm cha, tài khoản), rồi rollback toàn bộ; mọi commit
  bị chặn; Stock Reconciliation chỉ insert, không submit. Chạy `bench --site local.com clear-cache` sau trial.
- `apply`: ghi + commit từng bước; chạy lại an toàn (idempotent).

## Lệnh (Ubuntu / WSL)

```bash
REPO="/mnt/c/Users/ADMIN/OneDrive/Pictures/Năm 4 UIT/ERPNEXT/PROJECTPOS"
cd ~/frappe-bench
env/bin/python "$REPO/tools/seed/clean.py" --check-urls             # làm sạch, đọc clean/report.txt
PYTHONPATH="$REPO/tools" bench --site local.com execute seed.run.main --kwargs "{'mode': 'dry-run'}"
PYTHONPATH="$REPO/tools" bench --site local.com execute seed.run.main --kwargs "{'mode': 'trial'}"
bench --site local.com clear-cache
bench --site local.com backup                                        # trước lần apply đầu tiên
PYTHONPATH="$REPO/tools" bench --site local.com execute seed.run.main --kwargs "{'mode': 'apply'}"
PYTHONPATH="$REPO/tools" bench --site local.com execute seed.run.main --kwargs "{'mode': 'dry-run'}"  # phải toàn skipped
```

Thêm vào `--kwargs`: `'until': 's07_mode_of_payment'`, `'only': 's01_uom,s02_item_group'`,
`'with_demo_customers': 1`, `'with_suppliers': 1`.

Dự phòng nếu `bench execute` không thấy module `seed`:

```bash
cd ~/frappe-bench/sites && ../env/bin/python "$REPO/tools/seed/run.py" --site local.com --mode dry-run
```

Test (mỗi file một hàm loader, dữ liệu `ZZTEST-`, tự dọn trong finally):

```bash
for t in t_uom t_item_group t_item_variant t_price; do
  PYTHONPATH="$REPO/tools" bench --site local.com execute seed.tests.$t.run; done
PYTHONPATH="$REPO/tools" bench --site local.com execute seed.tests._util.leftovers   # phải ra {}
python -c "import sys; sys.path.insert(0, '$REPO/tools'); from seed.tests.t_rename import run; run()"  # không cần site
```

## Kiểm tra sau apply

| Bước | Kiểm tra |
|---|---|
| clean | `--check-urls`: 0 lỗi, 35/35 URL OK |
| s01–s04 | UOM mới có Symbol; cây Item Group 3 cấp; 3 Branch có `company`; 3 Cost Center dưới Cost Center gốc của Company |
| s05–s07 | 18 tài khoản chi nhánh; kho con có Account `Stock - Chi nhánh LC … - LC`; **6 Mode of Payment** (3 Cash + 3 QR Bank Transfer), mỗi cái 1 tài khoản đúng chi nhánh |
| s09–s10 | Mọi Item / biến thể có ảnh (không còn ảnh hỏng); TP-006 có 3 biến thể S/M/L |
| s11–s12 | Mỗi Price List bán 26 giá, mỗi Price List mua 29 giá; TP-006-L = 40.000 |
| s13 | "Khách vãng lai": nhóm Khách lẻ, Territory Vietnam, không Loyalty Program |
| s14 | Stock Balance mỗi kho 29 mã; giá trị 3.722.500 / 2.963.500 / 2.366.500 |

Test case (Van chạy):

- [TC1] dry-run rồi trial -> 14 bước không error; sau trial site không có Item mới
- [TC2] apply -> Mode of Payment "QR Bank Transfer - Chi nhánh LC Thủ Đức": Type Bank, tài khoản "Bank - Chi nhánh LC Thủ Đức - LC"
- [TC3] apply -> Item TP-003-M có field image là URL, ảnh hiện trên Desk
- [TC4] dry-run lại sau apply -> mọi bước created = 0, updated = 0
- [TC5] Stock Balance -> 3 kho x 29 mã, giá trị khớp bảng trên

## Rollback

```bash
ls -t ~/frappe-bench/sites/local.com/private/backups/*-database.sql.gz | head -1
bench --site local.com restore <file -database.sql.gz vừa backup>
bench --site local.com migrate && bench restart
```
