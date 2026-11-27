# Script tự kiểm (`mypos/selfcheck/`)

Script kiểm trên **site thật đã cài app** (không phải unit test). Thư mục tên `selfcheck` (không phải `tests`, file không bắt đầu
bằng `test_`) để `bench run-tests` không tự quét.

Quy ước mỗi script:

- Đúng **một hàm** cấp module; hằng số, import và hàm phụ (vd. `retry_deadlock`) đặt trong hàm (dán được vào `bench console` nếu cần).
- Dữ liệu thử có tiền tố `ZZTEST` / `zz.test.*`; dọn trong `finally`; lỗi dọn chỉ in `WARN` + cách xóa tay.
- Không đặt tên hàm trùng magic của IPython (`run`, `time`, `load`...).
- Dòng cuối luôn in `KẾT QUẢ: x/y PASS` (hoặc tương đương).

## Cách chạy

```bash
cd ~/frappe-bench
bench --site local.com execute mypos.selfcheck.<file>.<hàm> --kwargs "{'tham_so': 'giá trị', ...}"
```

- Kết quả **in ra terminal** (stdout của lệnh `bench execute`): từng dòng `PASS` / `FAIL` / `SKIP` / `WARN`, cuối cùng `KẾT QUẢ`.
  Giá trị trả về (nếu có) được `bench execute` in thêm ở cuối dạng JSON.
- `bench execute` commit sau khi hàm chạy xong; các script tự dọn dữ liệu thử trước khi trả về.
- Chạy trên site có dữ liệu cấu hình thật (POS Profile, Branch, MYPOS Menu, Mode of Payment) nhưng không đụng ca / đơn / khách thật,
  trừ ghi chú riêng trong docstring của từng hàm. **Đọc docstring trước khi chạy** (`sed -n 1,30p mypos/selfcheck/<file>.py`).
- Thay tham số `<...>` bằng dữ liệu của site. Có thể truyền vị trí: `--args "['POS A', 'MA-MON', 'Cash']"`.

## Danh sách

| File → hàm | Tham số | Kiểm |
|---|---|---|
| `branch_profile_check.check_branch_profile` | `pos_profile` | POS Profile bắt buộc Branch, 1 profile đang bật / Branch, chọn profile, Error Log SePay, ảnh `/order` |
| `walk_in_customer_check.check_walk_in_customer` | `pos_profile, item_code, mode_of_payment, price_list=None` | Khách vãng lai theo POS Profile |
| `table_card_check.check_table_card` | như trên | Thẻ bàn giữ / nhả theo đơn, hàng chờ thông báo thu ngân |
| `draft_cancel_check.check_draft_cancel` | như trên | Chặn đóng ca khi còn Draft, hủy = Cancelled + lý do, job tự hủy, tiền về sau hủy |
| `open_orders_check.check_open_orders` | như trên | Đóng ca chặn đơn Paid chưa giao, trạng thái kết thúc có lý do |
| `shift_owner_check.check_shift_owner` | như trên | Mở / đóng ca của chính mình, MANAGER thao tác thay |
| `payment_status_check.check_payment_status` | như trên | `payment_status`: tiền mặt / Desk / QR Đang chờ / hủy / trả hàng / webhook |
| `customer_display_check.check_customer_display` | như trên | Màn khách `/pos/customer` |
| `order_status_check.check_order_status` | như trên | Màn theo dõi đơn `/pos/status` |
| `poll_load_check.check_poll_load` | như trên + `rounds=20` | Phiên bản thay đổi theo POS Profile, realtime, đo SQL / ms |
| `orders_shift_check.check_orders_shift` | `item_code, mode_of_payment, branch_name=None, price_list=None, customer=None, cleanup=True` | Orders: Ca hiện tại / Lịch sử |
| `legacy_options_check.check_legacy_options` | `item_plain, item_with_options, mode_of_payment, branch_name=None, price_list=None` | `options` '[]' vs NULL, cột đường / đá cũ |
| `surcharge_check.check_option_surcharge` | `mode_of_payment, price_list, esp1, branch_name=None, customer=None, free_item_code=None` | Phụ thu topping sau CTKM (`esp1` = mã món có CTKM theo qty) |
| `kitchen_desk_check.check_kitchen_desk` | `cleanup=True` | POS KITCHEN vào Desk, chặn API bán hàng theo role |
| `order_qr_selftest.run_order_qr_selftest` | `branch=None` | Web đặt món QR (backend) |
| `order_history_selftest.run_order_history_selftest` | `branch=None, run_old=True` | "Đơn của tôi" theo khách + giỏ (gọi lại bộ QR) |
| `workspace_shortcut_check.check_workspace_shortcuts` | — | 4 workspace MYPOS: shortcut, roles (chỉ đọc) |
| `desktop_icon_check.check_desktop_icons` | — | 4 Desktop Icon: tồn tại (cần chế độ lưới icon), app, roles, link trỏ Workspace / route có thật (chỉ đọc) |
| `sidebar_check.check_sidebar` | — | Sidebar "MYPOS": module / app / standard, 4 mục Workspace có thật, không mục thừa, không trùng (chỉ đọc) |

Ví dụ:

```bash
bench --site local.com execute mypos.selfcheck.workspace_shortcut_check.check_workspace_shortcuts
bench --site local.com execute mypos.selfcheck.table_card_check.check_table_card \
  --kwargs "{'pos_profile': 'POS Chi nhanh 1', 'item_code': 'CF-SUA-M', 'mode_of_payment': 'Cash'}"
```

## Kiểm thêm sau khi cài

```bash
# quyền 3 role (chỉ thêm phần thiếu; in "[mypos_roles] ...")
bench --site local.com execute mypos.setup.roles.setup_roles_and_permissions
```

## Dọn dữ liệu khi deadlock

Mọi script ghi dữ liệu thử dọn trong `finally`, mỗi lần xóa thử lại tối đa 3 lần khi `QueryDeadlockError` (rollback, chờ 1 giây) và commit
ngay sau khi xóa được. Vẫn lỗi → in `WARN` + cách xóa tay; dòng `KẾT QUẢ` luôn được in.
`order_history_selftest` (khi `run_old=True`) tự import và chạy tiếp `order_qr_selftest`.
