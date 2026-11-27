# CLAUDE.md — app MYPOS

Đọc trước khi sửa code trong repo này.

- Sản phẩm: POS F&B dùng chung (white-label) trên ERPNext v16. **Không hardcode** tên quán, logo, màu thương hiệu: mọi thông tin
  thương hiệu đọc từ `Branch` (chi nhánh của `POS Profile.branch`).
- Kiến trúc, cấu trúc thư mục, mục lục quy tắc: [docs/README.md](docs/README.md).
- Quy ước code (tên DocType / field, module `MYPOS`, checklist DocType JSON, hook, import path `mypos.mypos.*`): [docs/code-standards.md](docs/code-standards.md).
- Quy tắc nghiệp vụ từng phần: `docs/rules/*.md` — đọc file tương ứng trước khi sửa phần đó.
- Cài / cấu hình: [docs/install.md](docs/install.md); triển khai: [docs/deploy.md](docs/deploy.md); script tự kiểm: [docs/testing.md](docs/testing.md).

Nguyên tắc không được vi phạm:

1. Giữ nguyên DocType lõi ERPNext; giao dịch là `POS Invoice`. Chỉ mở rộng bằng DocType `MYPOS *` (module `MYPOS`) hoặc Custom Field
   trên DocType chuẩn (khai báo trong `fixtures` của `hooks.py`, file trong `mypos/fixtures/`).
2. Trạng thái pha chế ở `custom_kitchen_status`, chỉ đặt khi `POS Invoice.status == "Paid"`; không đụng field `status` gốc.
3. Quyền của 3 role MYPOS: CHỈ ở `mypos/setup/roles.py` (`PERMS`), không dùng fixture Custom DocPerm.
4. Code ghi `POS Invoice` bằng `set_value` / SQL phải gọi `change_feed.bump(pos_profile)` (`docs/rules/realtime.md`).
5. Thay đổi cần chạy trên site đang có dữ liệu → viết patch mới trong `mypos/patches/` + `patches.txt`; thiết lập cho site cài mới →
   `mypos/setup/install.py` (`install-app` không chạy patch).
6. Không commit secret (API key SePay, `site_config.json`), không commit output build (`mypos/public/pos`, `mypos/public/order`).
