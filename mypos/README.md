### MYPOS

POS bán hàng tại quầy cho doanh nghiệp F&B (quán cà phê, trà sữa...), chạy trên ERPNext v16.
Không thay thế bán hàng / kế toán chuẩn: giao dịch là `POS Invoice` của ERPNext, app chỉ mở rộng thêm
(loại đơn, trạng thái pha chế, thẻ bàn, tùy chọn món, VietQR qua SePay, web đặt món QR, màn khách, màn theo dõi đơn).

Mọi thông tin thương hiệu (tên quán, logo, SĐT, địa chỉ, SePay) là **dữ liệu cấu hình của `Branch`**, không viết cứng trong code.

### Yêu cầu

- Frappe và ERPNext `>=16.50, <17` (đã chạy trên 16.61.0). Không cần HRMS (`Branch` thuộc ERPNext).
- Node.js + npm để build frontend (`pos/`).

### Cài đặt

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch version-16
bench --site <site> install-app mypos
cd apps/mypos/pos && npm install && npm run build && cd -
bench build --app mypos
bench --site <site> migrate
```

Chi tiết (cấu hình sau khi cài, host_name, socket.io, kiểm tra): [docs/install.md](docs/install.md).

### Tài liệu

- [docs/README.md](docs/README.md) — mục lục: kiến trúc, quy tắc nghiệp vụ từng phần, phân quyền, triển khai.
- [docs/testing.md](docs/testing.md) — chạy các script tự kiểm (`mypos/selfcheck/`).
- [pos/README.md](pos/README.md) — frontend React.

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/mypos
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit
