# Script tự kiểm (`mypos/selfcheck/`)

Script kiểm trên **site thật đã cài app** (không phải unit test). Thư mục tên `selfcheck` (không phải `tests`, file không bắt đầu bằng
`test_`) để `bench run-tests` không tự quét. Chạy được cả khi site **chưa có dữ liệu quán**: test ghi dữ liệu tự dựng "quán thử" tạm.

Quy ước mỗi script:

- Đúng **một hàm** cấp module; hằng số, import và hàm phụ (vd. `retry_deadlock`) đặt trong hàm (dán được vào `bench console`).
- Không đặt tên hàm trùng magic của IPython (`run`, `time`, `load`...).
- Dữ liệu thử có tiền tố `ZZTEST` / `zz.test.*`; dọn trong `finally`: mỗi lần xóa thử lại tối đa 3 lần khi `QueryDeadlockError` (rollback,
  chờ 1 giây), commit ngay; còn sót → in `WARN` + cách xóa tay.
- In từng dòng `PASS` / `FAIL` (vài script cũ dùng `OK`) / `SKIP`, dòng cuối `KẾT QUẢ: ...`.

## 1. Phân loại

| Loại | Script → hàm | Cần dữ liệu quán? |
|---|---|---|
| Điều kiện nền (chỉ đọc) | `prereq_check.check_prereq` | Không |
| **Chỉ đọc** | `apps_screen_check.check_apps_screen` (user có sẵn; thiếu user cho role → SKIP role đó) | Không |
| | `sidebar_check.check_sidebar` (gồm thứ tự Admin, Manager, Cashier, Kitchen) | Không |
| | `desktop_icon_check.check_desktop_icons` (chế độ Apps: SKIP phần DB) | Không |
| | `workspace_shortcut_check.check_workspace_shortcuts` | Không |
| **Ghi, chỉ user tạm** | `apps_screen_roles_check.check_apps_screen_roles` (ô MYPOS + điểm đến theo từng role) | Không |
| | `kitchen_desk_check.check_kitchen_desk` (KITCHEN vào Desk, chặn API bán hàng) | Không |
| **Ghi, quán thử** (tự dựng nếu không truyền tham số) | `branch_profile_check.check_branch_profile` | Quán thử |
| | `walk_in_customer_check.check_walk_in_customer` | Quán thử |
| | `table_card_check.check_table_card` | Quán thử |
| | `draft_cancel_check.check_draft_cancel` | Quán thử |
| | `open_orders_check.check_open_orders` | Quán thử |
| | `shift_owner_check.check_shift_owner` | Quán thử |
| | `payment_status_check.check_payment_status` | Quán thử |
| | `customer_display_check.check_customer_display` | Quán thử |
| | `order_status_check.check_order_status` | Quán thử |
| | `poll_load_check.check_poll_load` | Quán thử |
| | `orders_shift_check.check_orders_shift` | Quán thử + ca mở |
| | `legacy_options_check.check_legacy_options` | Quán thử + ca mở |
| | `surcharge_check.check_option_surcharge` | Quán thử + ca mở + CTKM |
| | `order_qr_selftest.run_order_qr_selftest` | Quán thử + ca mở |
| | `order_history_selftest.run_order_history_selftest` (gọi tiếp bộ QR, `run_old=True`) | Quán thử + ca mở |
| Công cụ | `test_shop.zz_test_shop` (dựng / dọn / liệt kê quán thử), `check_everything.check_everything` (chạy gộp) | — |

Tổng: 1 điều kiện nền + 4 chỉ đọc + 2 ghi user tạm + 15 ghi quán thử = 22 test.

## 2. Điều kiện nền và cách tạo

`check_prereq` in từng mục OK / THIẾU (chặn) / CẢNH BÁO (không chặn). Thiếu mục chặn → mọi test "quán thử" **SKIP có lý do**.

| Mục | Chặn? | Cách tạo |
|---|---|---|
| DocType MYPOS *, 3 role POS | Có | `bench --site <site> migrate` |
| Company mặc định | Có | Setup Wizard ERPNext (`/app/setup-wizard`): Country Vietnam, Currency VND |
| Company dùng tiền **VND** | Có | MYPOS Menu tra giá cố định VND (`rules/menu.md` §2) |
| Tài khoản mặc định Company: phải thu, doanh thu, Cost Center, Write Off, Round Off (+ Cost Center), tiền mặt / ngân hàng | Có | Setup Wizard tạo sẵn; thiếu thì Company → tab Accounts |
| Năm tài chính chứa hôm nay | Có | Desk → Fiscal Year → New |
| Kho (Warehouse không phải nhóm) | Có | Setup Wizard tạo "Stores - <abbr>" |
| Mode of Payment loại Cash có tài khoản cho Company | Có | Desk → Mode of Payment → Cash → Accounts |
| Customer Group, Territory (không phải nhóm), Item Group "All Item Groups", UOM "Nos" | Có | Setup Wizard |
| POS Settings → Invoice Type = **POS Invoice** (mặc định ERPNext là "Sales Invoice") | Có | Desk → POS Settings → Invoice Type → Save |
| Redis cache | Có | `bench start` |
| Price List bán | Không | quán thử tự tạo Price List riêng |
| Scheduler | Không | `bench --site <site> enable-scheduler` |
| socket.io (`localhost:<socketio_port>`) | Không | `bench start` (thiếu: màn POS poll, không realtime) |

## 3. Quán thử (`test_shop.zz_test_shop`)

Test ghi dữ liệu gọi KHÔNG tham số → `zz_test_shop("create")` dựng, chạy test trên đó, `zz_test_shop("drop", tag)` dọn trong `finally`.
Truyền tham số (POS Profile / món / Branch có sẵn) → chạy trên dữ liệu đó như trước, không dựng quán thử.

Tag `ZZTEST-<MMDDHHMMSS><3 ký tự>`, gồm: Item Group, Price List (VND), 4 món không tồn kho (`-CF` 30.000, `-TS` 35.000 có Option Group
"Đường" legacy `sugar_level`, `-ESP` 39.000 có Pricing Rule tạm 2–3 ly −5% / ≥ 4 ly −10%, `-FREE` 20.000), Mode of Payment "<tag> Bank",
Customer "<tag> WI" (khách vãng lai), Branch (thương hiệu + SePay giả, API key ngẫu nhiên) + 2 thẻ bàn, POS Profile (Cash + Bank, Applicable for
Users = Administrator), MYPOS Menu; test cần ca: POS Opening Entry của Administrator. Không đụng dữ liệu thật; không đổi cấu hình site.

## 4. Cách chạy

Kết quả in ra terminal (stdout). `bench execute` commit sau khi hàm xong; các script tự dọn trước đó.

```bash
cd ~/frappe-bench
# điều kiện nền
bench --site local.com execute mypos.selfcheck.prereq_check.check_prereq
# chạy gộp (prereq -> chỉ đọc -> ghi user tạm -> ghi quán thử nếu prereq đạt), bảng PASS / FAIL / SKIP cuối
bench --site local.com execute mypos.selfcheck.check_everything.check_everything
bench --site local.com execute mypos.selfcheck.check_everything.check_everything --kwargs "{'include_write': False}"   # chỉ phần đọc
bench --site local.com execute mypos.selfcheck.check_everything.check_everything --kwargs "{'only': ['table_card_check']}"
# từng test (không tham số = quán thử tạm)
bench --site local.com execute mypos.selfcheck.sidebar_check.check_sidebar
bench --site local.com execute mypos.selfcheck.table_card_check.check_table_card
# trên dữ liệu có sẵn
bench --site local.com execute mypos.selfcheck.table_card_check.check_table_card \
  --kwargs "{'pos_profile': 'POS A', 'item_code': 'MA-MON', 'mode_of_payment': 'Cash'}"
```

Trong `bench --site local.com console`:

```python
# Cách 1 — import (khuyến nghị)
from mypos.selfcheck.check_everything import check_everything
rows = check_everything()

from mypos.selfcheck.table_card_check import check_table_card
check_table_card()

# Cách 2 — dán hàm: gõ %cpaste, dán TOÀN BỘ nội dung file (vd. mypos/selfcheck/sidebar_check.py), gõ -- rồi Enter, sau đó gọi:
check_sidebar()
```

Dữ liệu ghi trong console không tự commit; các script tự commit / rollback như khi chạy bằng `bench execute`.

## 5. Kết quả mong đợi

| Test | Site mới, chưa cấu hình (chỉ migrate) | Site đủ điều kiện nền |
|---|---|---|
| `check_prereq` | THIẾU (ít nhất POS Settings Invoice Type; chưa Setup Wizard → Company...) | ĐỦ điều kiện nền |
| `check_apps_screen` | PASS phần hook / Administrator / Guest; SKIP role chưa có user | PASS |
| `check_sidebar` | PASS (gồm thứ tự) | PASS |
| `check_desktop_icons` | PASS phần file, SKIP phần DB (chế độ Apps) | như trái |
| `check_workspace_shortcuts` | PASS | PASS |
| `check_apps_screen_roles` | PASS (user tạm, không cần dữ liệu) | PASS |
| `check_kitchen_desk` | PASS | PASS |
| 15 test quán thử | SKIP: "Thiếu điều kiện nền: ..." | PASS (mục cần SePay / Loyalty có thể in SKIP riêng) |

[Unverified] Quán thử chưa chạy trên site thật lúc viết tài liệu: lần chạy đầu có thể gặp ràng buộc ERPNext chưa tính tới; lỗi in rõ ở dòng
"LỖI dựng quán thử ..." và quán thử tự dọn phần đã tạo.

## 6. Lỗi thường gặp

| Hiện tượng | Xử lý |
|---|---|
| Mọi test quán thử SKIP "Thiếu điều kiện nền: Company mặc định" | Chạy Setup Wizard (Vietnam / VND), rồi `check_prereq` lại |
| SKIP "POS Settings → Invoice Type = POS Invoice" | Desk → POS Settings → Invoice Type = POS Invoice |
| SKIP "Company dùng tiền VND" | Dùng Company tiền VND (menu tra giá VND) |
| "LỖI dựng quán thử ...: ..." | Đọc thông báo (thường thiếu tài khoản mặc định của Company); sửa rồi chạy lại; quán thử đã tự dọn |
| `QueryDeadlockError` khi dọn | Script tự thử lại 3 lần; còn sót → mục 7 |
| socket.io không chạy | Chỉ cảnh báo; `bench start`; DEV mở site bằng `localhost` (`rules/realtime.md` §6) |
| `check_apps_screen` FAIL "hook ..." ngay sau copy | Khởi động lại bench (`bench start` / `bench restart`) để nạp `hooks.py` mới |
| `check_sidebar` FAIL thứ tự sau migrate | Nạp lại file Sidebar: `bench --site <site> execute frappe.modules.import_file.import_file_by_path --args "['<bench>/apps/mypos/mypos/mypos/sidebar/mypos/mypos.json']" --kwargs "{'force': True}"`, rồi clear-cache |

## 7. Dọn khi test dừng giữa chừng

```bash
# liệt kê dữ liệu thử còn sót (chỉ đọc)
bench --site local.com execute mypos.selfcheck.test_shop.zz_test_shop --kwargs "{'action': 'list'}"
# xóa mọi quán thử ZZTEST-* (đơn, ca, POS Profile gắn Branch thử, món, giá, CTKM, Option Group, khách, Mode of Payment, Branch)
bench --site local.com execute mypos.selfcheck.test_shop.zz_test_shop --kwargs "{'action': 'drop'}"
bench --site local.com execute mypos.selfcheck.test_shop.zz_test_shop --kwargs "{'action': 'drop', 'tag': 'ZZTEST-1127130501ABC'}"
```

Dữ liệu riêng của từng test (POS Profile "ZZTEST <tên test> ...", user `zz.test.*`) bình thường do chính test dọn. Còn sót thì trong
`bench --site local.com console`:

```python
import frappe
for u in frappe.get_all("User", filters={"name": ["like", "zz.test.%"]}, pluck="name"):
    for c in frappe.get_all("Contact", filters={"user": u}, pluck="name"):
        frappe.delete_doc("Contact", c, force=1, ignore_permissions=True)
    frappe.delete_doc("User", u, force=1, ignore_permissions=True)
frappe.db.commit()
print(frappe.get_all("POS Profile", filters={"name": ["like", "ZZTEST%"]}, pluck="name"))   # xóa tay sau khi hủy / xóa đơn của chúng
```
