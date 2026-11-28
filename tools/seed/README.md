# tools/seed — nạp dữ liệu demo vào site dev

Không nằm trong app `mypos`. Dữ liệu nguồn `DATA/` và dữ liệu sạch `tools/seed/clean/` không commit (.gitignore).
Quyết định nghiệp vụ: Q1-Q12 (2026-11-28), mapping ở `config.py`.

## Thứ tự

| Bước | Việc | Ghi chú |
|---|---|---|
| `clean.py` | `DATA/` -> `clean/*.csv`, `report.txt`, `stock_mapping.csv` | Python thuần, không cần site |
| s01_uom | UOM mới (Ly, Lon, Phần, Cái, Thùng, Chai); Litre / Millilitre / Gram / Kg chỉ kiểm tra | Q3 |
| s02_item_group | 15 Item Group | |
| s03_branch | 3 Branch, `company` = Company của site | Q2 |
| s04_warehouse | `Hệ thống Cửa hàng - <abbr>` + 3 kho | |
| s05_attribute | Chỉ kiểm tra Size Medium = M, Large = L | Q5 |
| s06_item | 43 Item (9 template) | |
| s07_variant | 18 biến thể `<mã>-M` / `-L` | Q4 |
| s08_price | 26 giá bán + 26 giá mua | chỉ sheet "Selling price" / "Buying price" |
| s09_customer | "Khách lẻ (Walk-in Customer)" | |
| s10_payment | Account `Ngân hàng - <abbr>` + gắn Wire Transfer; kiểm tra Cash, Cost Center | Q10 |
| s11_opening_stock | 3 Stock Reconciliation Opening Stock (sheet "Stock entry (lần 1 - test POS)") | Q6, Q8, Q9 |

POS Profile + MYPOS Menu (Q11): làm sau khi Van duyệt kết quả s11.

## Lệnh (Ubuntu / WSL)

```bash
REPO="/mnt/c/Users/ADMIN/OneDrive/Pictures/Năm 4 UIT/ERPNEXT/PROJECTPOS"
cd ~/frappe-bench
env/bin/python "$REPO/tools/seed/clean.py"                       # làm sạch, đọc report
PYTHONPATH="$REPO/tools" bench --site local.com execute seed.run.main --kwargs "{'mode': 'dry-run'}"
bench --site local.com backup                                      # trước lần apply đầu tiên
PYTHONPATH="$REPO/tools" bench --site local.com execute seed.run.main --kwargs "{'mode': 'apply'}"
PYTHONPATH="$REPO/tools" bench --site local.com execute seed.run.main --kwargs "{'mode': 'dry-run'}"  # phải toàn skipped
```

Một phần: `--kwargs "{'mode': 'dry-run', 'only': 's01_uom,s02_item_group'}"` hoặc `'until': 's05_attribute'`.

Dự phòng nếu `bench execute` không thấy module `seed`:

```bash
cd ~/frappe-bench/sites && ../env/bin/python "$REPO/tools/seed/run.py" --site local.com --mode dry-run
```

Test (mỗi file một hàm, dữ liệu `ZZTEST-`, tự dọn):

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
