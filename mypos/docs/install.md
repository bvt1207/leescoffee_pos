# Cài MYPOS trên bench mới

## 1. Yêu cầu

- Bench có `frappe` và `erpnext` bản `>=16.50, <17` (đã chạy trên 16.61.0). **Không cần HRMS.**
- Node.js + npm (build frontend), Redis (cache, realtime), tiến trình `socketio` của bench (realtime, không bắt buộc: có poll dự phòng).

## 2. Cài

```bash
cd ~/frappe-bench
bench get-app <URL repo mypos> --branch <branch>
bench --site local.com backup                     # site đang có dữ liệu thì sao lưu trước
bench --site local.com install-app mypos
cd apps/mypos/pos && npm install && npm run build && cd ~/frappe-bench
bench build --app mypos
bench --site local.com migrate
bench --site local.com clear-cache
# DEV: Ctrl+C rồi `bench start` lại. Production: `sudo supervisorctl restart all` (hoặc `bench restart`).
```

#### `npm install` trên Linux báo thiếu gói nhị phân

`pos/package-lock.json` được sinh trên Windows (npm 10.9, node 22). Nếu `npm install` / `npm run build` trên Linux báo thiếu gói
nhị phân theo nền tảng (vd. `@esbuild/linux-x64`, `@rollup/rollup-linux-x64-gnu`: "Cannot find module ..."), sinh lại lock trên Linux:

```bash
cd ~/frappe-bench/apps/mypos/pos
rm -rf node_modules package-lock.json
npm install
npm run build
```

Rồi copy `package-lock.json` mới về repo và commit (lock sinh trên Linux dùng cho cả hai nền tảng).

`install-app` tự làm (không cần patch):

| Thành phần | Nguồn |
|---|---|
| Module Def "MYPOS", 8 DocType `MYPOS *` | `modules.txt` + JSON trong `mypos/mypos/doctype/` |
| 35 Custom Field (POS Invoice, POS Invoice Item, POS Profile, Branch, Customer.mobile_number), 1 Property Setter, 3 Role | `mypos/fixtures/` |
| Quyền DocType của 3 role | `after_install` → `mypos/setup/roles.py` (`PERMS`) |
| 4 Workspace, Sidebar "MYPOS", 4 Desktop Icon | JSON trong app |
| Cron 5 phút tự hủy Draft quá hạn | `hooks.scheduler_events` (cần `bench --site local.com enable-scheduler`) |

Mỗi lần `bench migrate`: `after_migrate` bổ sung role / quyền còn thiếu theo `PERMS` (chỉ thêm, lỗi chỉ ghi Error Log).

## 3. Cấu hình tay sau khi cài (theo thứ tự)

Không có dữ liệu mẫu trong code. Mọi mục dưới đây nhập trên Desk; đánh dấu `[x]` khi xong.

1. [ ] **Company, Warehouse, Price List, Item / Item Price, Mode of Payment** (chuẩn ERPNext): 1 mode tiền mặt + 1 mode chuyển khoản (`type = Bank`, có tài khoản).
2. [ ] **Branch** (`docs/rules/branch.md` §5): `company`, `brand_name`, `brand_logo` (file **public**), `brand_phone`, `brand_address`;
   SePay: `sepay_enabled`, `sepay_va_account`, `sepay_bank_code`, `sepay_api_key` (trùng key cấu hình webhook bên SePay).
3. [ ] **Customer khách vãng lai**: Customer Group Individual, không SĐT, không Loyalty Program (`docs/rules/pos_profile.md` §5).
4. [ ] **POS Profile** (mỗi Branch đúng 1 profile đang bật): `company`, `warehouse`, `selling_price_list`, `currency`, **`branch`**,
   `custom_walk_in_customer`, Payments (2 mode ở bước 1), `income_account` (phụ thu topping).
5. [ ] **User + Role**: thu ngân `POS CASHIER`; pha chế `POS KITCHEN`; quản lý `POS MANAGER` (+ `Sales User`, `Sales Manager`, `Stock User`,
   `Auditor` nếu cần, `docs/rules/roles.md` §1). Tài khoản TV `/pos/status`: POS KITCHEN riêng.
6. [ ] **POS Profile → Applicable for Users**: mọi thu ngân, quản lý bán hàng **và mọi tài khoản pha chế**; mỗi user `default` ở đúng 1 profile.
   Nhiều chi nhánh: User Permission `POS Profile` cho từng quản lý.
7. [ ] **MYPOS Menu** cùng Price List của POS Profile; **MYPOS Option Group** (đường / đá / topping) nếu dùng (`docs/rules/options.md` §6).
8. [ ] **MYPOS Buzzer** (thẻ bàn) gắn Branch; **MYPOS Order QR** gắn Branch (in mã từ form); **MYPOS Banner** (ảnh public, 16:9).
9. [ ] **POS Settings** (ERPNext): `invoice_type = POS Invoice` (đóng ca gộp POS Invoice).
10. [ ] **host_name** của site (URL trong mã QR đặt món, `docs/deploy.md` §3):
    `bench --site local.com set-config host_name "http://<host>:<port>"`. Đổi host thì in lại mã QR.
11. [ ] Webhook SePay: URL `https://<host>/api/method/mypos.mypos.doctype.sepay.sepay.sepay_webhook` (`docs/rules/sepay.md`, `order-qr.md` §3).
12. [ ] Scheduler bật: `bench --site local.com scheduler status` (disabled → `bench --site local.com enable-scheduler`).

Kiểm nhanh (bench console, chỉ đọc):

```python
frappe.get_all("POS Profile", fields=["name", "branch", "disabled", "custom_walk_in_customer", "selling_price_list"])
frappe.db.get_value("DocType", "MYPOS Menu", "module")          # "MYPOS"
frappe.get_all("Custom Field", filters={"module": "MYPOS"}, pluck="name")   # 35 dòng
```

## 4. Kiểm tra

Script tự kiểm: [testing.md](testing.md). Kiểm tay theo từng màn (cột PASS / FAIL): [checklist.md](checklist.md). Màn hình: `/pos`, `/pos/orders`, `/pos/kitchen`, `/pos/customer`, `/pos/status`, `/order/<token>`.
