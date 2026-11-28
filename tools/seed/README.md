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
| s15_demo_customer | Khi `--with-demo-customers` (lệnh bên dưới BẬT): khách mẫu @example.com + Contact | 14 (12 thành viên + 2 doanh nghiệp) |
| s16_supplier | Khi `--with-suppliers` (lệnh bên dưới BẬT): Supplier Group + Supplier | 3 + 7 |

`run.py` mặc định TẮT 2 cờ (script dùng chung); môi trường local này nạp luôn dữ liệu mẫu (quyết định Van 2026-11-28),
nên mọi lệnh dry-run / trial / apply bên dưới truyền cùng biến `$FLAGS`.

File nguồn đã mang tên mới ("Chi nhánh LC ...", "QR Bank Transfer - ..."); `clean.py` vẫn nhận file cũ (A/B/C,
"Transfer - ...") và đổi tên idempotent (`tests/t_rename.py`).

Giai đoạn 2 (sau khi Van duyệt): POS Profile x 3 — Payment Methods mỗi chi nhánh gồm "Cash - Chi nhánh LC ..." (Default)
+ "QR Bank Transfer - Chi nhánh LC ..." của chính chi nhánh; MYPOS Menu. Sửa mypos để Mode of Payment đi theo POS Profile:
để sau. Giai đoạn 3: Product Bundle (`clean/product_bundle.csv`).

## Cách chạy

KHÔNG dùng `bench execute seed...`: Frappe coi phần đầu đường dẫn là tên app (`AppNotInstalledError: App seed is not
installed`). Chạy `run.py` / `run_tests.py` độc lập bằng python của bench, từ `~/frappe-bench/sites`. Script tự
`frappe.init` + `frappe.connect` + `frappe.set_user("Administrator")`, tắt gửi email, và luôn rollback phần chưa commit
rồi `frappe.destroy()` khi kết thúc (kể cả lỗi / Ctrl+C). Dùng đường dẫn tuyệt đối `~/frappe-bench/env/bin/python`
(gọi `../env/bin/python` làm Python 3.14 in cảnh báo `sys.prefix`, vô hại). `bench --site ...` (backup, clear-cache,
restore) chạy từ `~/frappe-bench`.

- `--mode dry-run` (mặc định): so với site, không ghi.
- `--mode trial`: ghi tạm để ERPNext validate thật (bắt lỗi như URL ảnh, nhóm cha, tài khoản, Territory), rồi rollback
  toàn bộ — kể cả khi lỗi giữa chừng; mọi commit bị chặn; Stock Reconciliation chỉ insert, không submit.
  Sau trial chạy `bench --site local.com clear-cache`.
- `--mode apply`: commit sau mỗi bước thành công; lỗi -> rollback bước đó và dừng; chạy lại an toàn (idempotent).
- Khác: `--until s07_mode_of_payment`, `--only s01_uom,s02_item_group`, `--company` (site > 1 Company), `--sites-path`.
  Mã thoát 1 khi có lỗi.

## Lệnh (Ubuntu / WSL)

```bash
REPO="/mnt/c/Users/ADMIN/OneDrive/Pictures/Năm 4 UIT/ERPNEXT/PROJECTPOS"
PY="$HOME/frappe-bench/env/bin/python"
FLAGS="--with-demo-customers --with-suppliers"

cd ~/frappe-bench/sites
"$PY" "$REPO/tools/seed/clean.py" --check-urls                                    # 1) làm sạch, đọc clean/report.txt
"$PY" "$REPO/tools/seed/run.py" --site local.com --mode dry-run $FLAGS             # 2)
"$PY" "$REPO/tools/seed/run.py" --site local.com --mode trial $FLAGS               # 3)
cd ~/frappe-bench && bench --site local.com clear-cache                            # 4)
# --- dừng, kiểm tra kết quả ---
cd ~/frappe-bench && bench --site local.com backup                                 # 5) trước lần apply đầu tiên
cd ~/frappe-bench/sites && "$PY" "$REPO/tools/seed/run.py" --site local.com --mode apply $FLAGS    # 6)
cd ~/frappe-bench/sites && "$PY" "$REPO/tools/seed/run.py" --site local.com --mode dry-run $FLAGS  # 7) toàn skipped
```

`$FLAGS` cố ý không đặt trong nháy kép (để tách thành 2 tham số).

Test (mỗi file một hàm loader, dữ liệu `ZZTEST-`, tự dọn trong finally; GHI vào site rồi tự xóa — chạy sau khi backup):

```bash
cd ~/frappe-bench/sites && "$PY" "$REPO/tools/seed/run_tests.py" --site local.com   # in PASS/FAIL + ZZTEST- còn sót {}
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
| s15 | Customer: 15 (1 "Khách vãng lai" + 14 khách mẫu: 12 nhóm Khách thành viên, 2 nhóm Khách doanh nghiệp); đủ 3 Customer Group; mỗi khách mẫu 1 Contact email @example.com |
| s16 | Supplier Group: 3 nhóm file (dưới All Supplier Groups); Supplier: 7, mỗi NCC đúng nhóm |

Test case (Van chạy):

- [TC1] dry-run rồi trial (`run.py ... $FLAGS`) -> 16 bước không error; sau trial site không có Item / Customer / Supplier mới
- [TC2] apply -> Mode of Payment "QR Bank Transfer - Chi nhánh LC Thủ Đức": Type Bank, tài khoản "Bank - Chi nhánh LC Thủ Đức - LC"
- [TC3] apply -> Customer list: 15 khách (lọc Customer Group: Khách lẻ 1, Khách thành viên 12, Khách doanh nghiệp 2); Supplier list: 7
- [TC4] dry-run lại sau apply (`run.py ... $FLAGS`) -> mọi bước created = 0, updated = 0
- [TC5] Stock Balance -> 3 kho x 29 mã, giá trị khớp bảng trên; Item TP-003-M có ảnh trên Desk

## Giai đoạn 2 — thu ngân thử, POS Profile, MYPOS Menu (`--stage 2`)

Quyết định Van 2026-11-28: 3 user thu ngân thử; menu đủ 10 món; tên "POS - Chi nhánh LC ..." / "Menu - Chi nhánh LC ...";
chưa cấu hình SePay (script không ghi secret).

| Bước | Việc | Số |
|---|---|---|
| s17_cashier_user | `thungan.nguyenhue / thungan.leloi / thungan.thuduc @example.com`, role POS CASHIER, không mật khẩu, không email | 3 |
| s18_pos_profile | "POS - Chi nhánh LC ...": kho con, Price List bán, Branch, khách vãng lai, Cost Center, TK Sales / COGS / Write Off / Cash (tiền thừa) của chi nhánh; Payments = Cash (Default) + QR Bank Transfer của chi nhánh; Applicable for Users = thu ngân thử của chi nhánh (Default) | 3 |
| s19_mypos_menu | "Menu - Chi nhánh LC ...", Price List bán của chi nhánh, 10 món: TP-003..TP-010 (template, POS hiện S/M/L), TP-002, TP-001 | 3 |

```bash
REPO="/mnt/c/Users/ADMIN/OneDrive/Pictures/Năm 4 UIT/ERPNEXT/PROJECTPOS"
PY="$HOME/frappe-bench/env/bin/python"
cd ~/frappe-bench/sites && "$PY" "$REPO/tools/seed/run.py" --site local.com --mode dry-run --stage 2
cd ~/frappe-bench/sites && "$PY" "$REPO/tools/seed/run.py" --site local.com --mode trial --stage 2
cd ~/frappe-bench && bench --site local.com clear-cache
# --- dừng, kiểm tra ---
cd ~/frappe-bench && bench --site local.com backup
cd ~/frappe-bench/sites && "$PY" "$REPO/tools/seed/run.py" --site local.com --mode apply --stage 2
cd ~/frappe-bench/sites && "$PY" "$REPO/tools/seed/run.py" --site local.com --mode dry-run --stage 2   # toàn skipped
```

Kiểm tra sau apply: 3 POS Profile đang bật, mỗi Branch đúng 1 profile; Payments 2 dòng (Cash mặc định); 3 MYPOS Menu,
mỗi menu 10 món; đăng nhập thu ngân thử mở `/pos` thấy tab Cà phê / Trà / Trà sữa / Đồ uống / Bánh ngọt, món có size S/M/L.

### Thử bán: Mode of Payment ghi vào hóa đơn là gì?

Mục đích: kiểm nghi vấn "mypos lấy Mode of Payment đầu tiên theo tên trên toàn công ty, không theo POS Profile"
(`pos_api._get_payment_modes` / `_resolve_mode_of_payment`; giao diện /pos không có ô chọn mode khi tạo đơn).
Mode được gán LÚC TẠO ĐƠN (Draft), trước khi chọn "Thu tiền mặt" / "Thanh toán QR".

1. Desk (Administrator) -> User -> `thungan.thuduc@example.com` -> mục Settings / Change Password -> đặt mật khẩu.
   Làm tương tự cho `thungan.nguyenhue@example.com`.
2. Cửa sổ ẩn danh, đăng nhập `thungan.thuduc@example.com`, mở `http://localhost:8002/pos`.
3. Đơn tiền mặt: chọn "Mang đi" -> Cà phê đen size M -> "Tạo đơn" -> màn Orders mở đúng đơn -> "Thu tiền mặt".
   Ghi lại mã đơn (ACC-PSINV-...).
4. Đơn QR: "Mang đi" -> Trà chanh size L -> "Tạo đơn" -> bấm "Thanh toán QR" -> kỳ vọng báo lỗi chưa cấu hình SePay
   (Branch chưa bật SePay). Ghi lại mã đơn (Draft), xem Payments (bước 6), rồi "Hủy đơn" (lý do "Đặt nhầm") để đơn
   Draft không chặn đóng ca.
5. Lặp 2-4 với `thungan.nguyenhue@example.com` (cửa sổ ẩn danh mới).
6. Xem Payments trên Desk: `http://localhost:8002/app/pos-invoice` -> lọc POS Profile -> mở đơn -> bảng "Payments"
   (cột Mode of Payment, Account). Hoặc xem nhanh cả 4 đơn (chỉ đọc):

```bash
cd ~/frappe-bench && bench --site local.com mariadb -e "select i.name, i.pos_profile, i.status, p.mode_of_payment, p.account, p.amount from \`tabPOS Invoice\` i join \`tabSales Invoice Payment\` p on p.parent = i.name and p.parenttype = 'POS Invoice' order by i.creation"
```

| Kết quả | Mode of Payment | Account |
|---|---|---|
| Đúng (theo POS Profile) | `Cash - Chi nhánh LC Thủ Đức` / `... Nguyễn Huệ` | `Cash - Chi nhánh LC ... - LC` |
| Sai (nghi vấn) | mode đầu tiên theo tên toàn công ty — [Inference] có thể là `Cash` (có sẵn của ERPNext) | `Cash - LC` |

Nếu sai: gửi yêu cầu sửa mypos riêng (chưa sửa code ở bước seed).

## Rollback

```bash
ls -t ~/frappe-bench/sites/local.com/private/backups/*-database.sql.gz | head -1
bench --site local.com restore <file -database.sql.gz vừa backup>
bench --site local.com migrate && bench restart
```
