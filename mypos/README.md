# MYPOS

POS (Point of Sale) cho chuỗi quán cà phê / đồ uống, chạy trên **Frappe / ERPNext v16**.

MYPOS dùng chính `POS Invoice`, `POS Profile`, ca POS và kế toán / kho của ERPNext; app chỉ mở rộng thêm phần vận hành quầy. Thông tin
thương hiệu (tên quán, logo, SĐT, địa chỉ, cấu hình SePay) là **dữ liệu của `Branch`**, không viết cứng trong code, nên một bản cài
dùng được cho nhiều doanh nghiệp / chi nhánh.

## Features

| Màn / chức năng | Mô tả |
|---|---|
| Bán món `/pos` | Menu theo Price List, size / tùy chọn món (đường, đá, topping có phụ thu), Mang đi / Tại quán, khách vãng lai, tích / đổi điểm Loyalty |
| Đơn hàng `/pos/orders` | Đơn trong ca, thu tiền mặt, VietQR chuyển khoản (SePay), hủy đơn có lý do, in hóa đơn / tem ly |
| Pha chế `/pos/kitchen` | Chưa làm → Đã làm → Đã hoàn thành; chỉ đơn đã thanh toán; thông báo thu ngân khi đơn xong |
| Thẻ bàn | Gán thẻ cho đơn Tại quán, tự trả thẻ khi đơn kết thúc |
| Đặt món QR `/order/<token>` | Khách tự đặt và chuyển khoản trên điện thoại, theo dõi "Đơn của tôi" |
| Màn khách `/pos/customer` | Giỏ hàng, tổng tiền, VietQR, banner quảng cáo |
| Màn theo dõi đơn `/pos/status` | Treo TV: Đang chuẩn bị / Sẵn sàng nhận món |
| Desk | Ô MYPOS trên màn Apps, workspace theo vai trò (Cashier / Kitchen / Manager / Admin), quản lý ca, chặn đóng ca khi còn đơn dở |

## Requirements

- Frappe và ERPNext **16.x** (`>=16.50, <17`); đã chạy trên 16.61.0. Không cần HRMS.
- Python theo `pyproject.toml` (`requires-python`), Node.js + npm để build frontend.
- Company dùng tiền **VND** (menu tra giá theo VND), POS Settings → Invoice Type = **POS Invoice**.

## Quick install

```bash
cd ~/frappe-bench
bench get-app https://github.com/bvt1207/mypos.git --branch version-16
bench --site <site> install-app mypos
bench --site <site> migrate
cd apps/mypos/pos && npm install && npm run build && cd -
bench build --app mypos
bench restart            # hoặc khởi động lại `bench start` khi chạy DEV
```

Cấu hình sau khi cài (Branch + thương hiệu + SePay, POS Profile, user / role, menu, thẻ bàn, mã QR, banner, `host_name`):
[docs/install.md](docs/install.md) §3. Triển khai thật (socket.io, nginx, treo TV): [docs/deploy.md](docs/deploy.md).

## Tests

Bộ script tự kiểm chạy trên site đã cài (kể cả site chưa có dữ liệu quán — test ghi dữ liệu tự dựng "quán thử" `ZZTEST-*` rồi tự dọn):

```bash
bench --site <site> execute mypos.selfcheck.prereq_check.check_prereq          # điều kiện nền, in cách tạo mục thiếu
bench --site <site> execute mypos.selfcheck.check_everything.check_everything  # chạy gộp, bảng PASS / FAIL / SKIP
```

Chi tiết: [docs/testing.md](docs/testing.md); kiểm tay theo màn: [docs/checklist.md](docs/checklist.md).

## Project structure

```text
pyproject.toml, README.md, license.txt, CLAUDE.md (quy ước cho trợ lý code)
docs/            cài đặt, triển khai, kiểm tra, quy tắc nghiệp vụ (docs/rules/)
pos/             frontend React + TypeScript (Vite) -> build ra mypos/public/{pos,order}
mypos/           package Python: hooks.py, setup/ (role + quyền), fixtures/, www/, public/, selfcheck/
mypos/mypos/     module "MYPOS": api/, doctype/ (MYPOS Menu, Option Group, Buzzer, Order QR, Banner + hook POS Invoice / ca / POS Profile),
                 workspace/, sidebar/
```

## Status

Phiên bản 0.1.0. Đã chạy trên Frappe / ERPNext 16.61.0: bộ selfcheck **23/23 PASS** trên site mới. Tồn đọng đã biết: [CLAUDE.md](CLAUDE.md)
(mục "Trạng thái").

## License

MIT — xem [license.txt](license.txt).
