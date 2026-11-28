# tools/seed — nạp dữ liệu demo vào site dev

Không nằm trong app `mypos`. Dữ liệu nguồn `DATA/` ("Data Test.xlsx" + `LC_TON_DAU_KY_ERPNext_V16.csv`) và dữ liệu sạch
`tools/seed/clean/` không commit (.gitignore). Quyết định: vòng 2 Q1-Q8 (2026-11-28), quy tắc ở `config.py`.

Đổi tên chi nhánh ở mọi nơi (Q5): "Chi nhánh A / B / C" -> "Chi nhánh LC Nguyễn Huệ / LC Lê Lợi / LC Thủ Đức".
Company / abbr / gốc cây Cost Center, Warehouse / tài khoản Temporary đọc từ site.

## Thứ tự

| Bước | Việc | Số bản ghi |
|---|---|---|
| `clean.py` | `DATA/` -> `clean/*.csv` + `report.txt` (Python thuần) | — |
| s01_uom | UOM mới Cái, Gói, Ly, Chai, Lon (+ Symbol); Litre / Millilitre / Gram chỉ kiểm tra | 5 tạo + 3 kiểm |
| s02_item_group | Cây 3 cấp | 20 |
| s03_branch | Branch, `company` = Company của site | 3 |
| s04_cost_center | Dưới Cost Center gốc của Company | 3 |
| s05_account | Cash / Stock / Bank / Sales / COGS / Write Off mỗi chi nhánh | 18 |
| s06_warehouse | 3 kho nhóm + 3 kho con gắn tài khoản Stock | 6 |
| s07_mode_of_payment | Cash / Transfer mỗi chi nhánh, gắn tài khoản bước 5 | 6 |
| s08_attribute | Chỉ kiểm tra Size Small = S, Medium = M, Large = L | 3 kiểm |
| s09_item | Không nạp ảnh (Q6); TP-002 giữ nhóm cha "Đồ uống" (Q7) | 37 (8 template) |
| s10_variant | `TP-xxx-S/M/L` | 24 |
| s11_price_list | Giá bán / giá mua mỗi chi nhánh | 6 |
| s12_item_price | | 78 bán + 87 mua |
| s13_customer | 3 Customer Group + "Khách vãng lai" (Territory Vietnam, Q8) | 3 + 1 |
| s14_opening_stock | Stock Reconciliation Opening Stock / kho chi nhánh, từ CSV | 3 chứng từ |

Làm SAU khi Van kiểm tra trên Desk: POS Profile x 3, MYPOS Menu, Product Bundle (`clean/product_bundle.csv`, Q4).

## Lệnh (Ubuntu / WSL)

```bash
REPO="/mnt/c/Users/ADMIN/OneDrive/Pictures/Năm 4 UIT/ERPNEXT/PROJECTPOS"
cd ~/frappe-bench
env/bin/python "$REPO/tools/seed/clean.py"                       # làm sạch, đọc clean/report.txt
PYTHONPATH="$REPO/tools" bench --site local.com execute seed.run.main --kwargs "{'mode': 'dry-run'}"
bench --site local.com backup                                      # trước lần apply đầu tiên
PYTHONPATH="$REPO/tools" bench --site local.com execute seed.run.main --kwargs "{'mode': 'apply'}"
PYTHONPATH="$REPO/tools" bench --site local.com execute seed.run.main --kwargs "{'mode': 'dry-run'}"  # phải toàn skipped
```

Một phần: thêm `'only': 's01_uom,s02_item_group'` hoặc `'until': 's07_mode_of_payment'` vào `--kwargs`.

Dự phòng nếu `bench execute` không thấy module `seed`:

```bash
cd ~/frappe-bench/sites && ../env/bin/python "$REPO/tools/seed/run.py" --site local.com --mode dry-run
```

Test (mỗi file một hàm loader, dữ liệu `ZZTEST-`, tự dọn trong finally):

```bash
for t in t_uom t_item_group t_item_variant t_price; do
  PYTHONPATH="$REPO/tools" bench --site local.com execute seed.tests.$t.run; done
PYTHONPATH="$REPO/tools" bench --site local.com execute seed.tests._util.leftovers   # phải ra {}
```

## Rollback

```bash
ls -t ~/frappe-bench/sites/local.com/private/backups/*-database.sql.gz | head -1
bench --site local.com restore <file -database.sql.gz vừa backup>
bench --site local.com migrate && bench restart
```
