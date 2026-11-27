# Chạy selfcheck MYPOS trên site chưa có dữ liệu quán (`local.com`)

Tài liệu đầy đủ (phân loại, quán thử, kết quả mong đợi, lỗi thường gặp, cách dọn): `mypos/docs/testing.md`.
File này là trình tự chạy trên bench DEV `~/frappe-bench`, site `local.com`, sau khi copy app (`tools/copy_mypos_steps.md`) và migrate.

## 1. Điều kiện nền

```bash
cd ~/frappe-bench
bench --site local.com execute mypos.selfcheck.prereq_check.check_prereq
```

Mỗi dòng THIẾU có sẵn cách tạo. Trên site vừa tạo thường cần:

1. Setup Wizard ERPNext (`http://localhost:8000/app/setup-wizard`): Country **Vietnam**, Currency **VND**, tạo Company
   (sinh sẵn tài khoản mặc định, Fiscal Year, kho "Stores - <abbr>", Mode of Payment Cash, Customer Group, Territory, UOM Nos).
2. Desk → **POS Settings** → Invoice Type = **POS Invoice** → Save (mặc định ERPNext là Sales Invoice).
3. `bench --site local.com enable-scheduler` (không bắt buộc cho test).
4. `bench start` đang chạy (Redis bắt buộc; socket.io chỉ cảnh báo).

Chạy lại `check_prereq` tới khi in "KẾT QUẢ: ĐỦ điều kiện nền".

## 2. Chạy

```bash
# chỉ phần không cần dữ liệu (chạy được ngay sau migrate, kể cả khi prereq THIẾU)
bench --site local.com execute mypos.selfcheck.check_everything.check_everything --kwargs "{'include_write': False}"
# toàn bộ: phần quán thử tự SKIP nếu prereq THIẾU
bench --site local.com execute mypos.selfcheck.check_everything.check_everything 2>&1 | tee ~/mypos_selfcheck_$(date +%Y%m%d-%H%M).log
```

Từng test, bench console, kết quả mong đợi: `mypos/docs/testing.md` §4–§5.

## 3. Dọn

```bash
bench --site local.com execute mypos.selfcheck.test_shop.zz_test_shop --kwargs "{'action': 'list'}"
bench --site local.com execute mypos.selfcheck.test_shop.zz_test_shop --kwargs "{'action': 'drop'}"
```

## 4. Gửi lại kết quả

Gửi phần **BẢNG KẾT QUẢ** cuối log (và các dòng `FAIL` / `LỖI` / `WARN` của test FAIL).
