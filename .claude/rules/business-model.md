# Mô hình nghiệp vụ — giai đoạn hiện tại (2 luồng)

> Tách nguyên văn từ CLAUDE.md mục 3 ngày 2026-11-27 (CLAUDE.md chỉ còn tham chiếu). Tự động tải mỗi phiên.
> Đường dẫn `.claude/rules/leescoffee_pos/*` trong file này là bản lịch sử; bản hiện hành của app `mypos`: `mypos/docs/rules/*` (CLAUDE.md mục 13).

**Không dùng "Table" (quản lý bàn Available/Occupied) như 1 entity có vòng đời.**

Hai field độc lập — cả hai là **Custom Field trên `POS Invoice`**:

- `order_type`: `Take Away` | `Dine In`
- `order_channel`: `POS` (nhân viên nhập tại quầy) | `QR` (khách tự đặt qua web `/order/<token>`,
  backend đã test Pass 2026-11-14, frontend đã code, đang test từng phần) — xem `.claude/rules/leescoffee_pos/order-qr.md`.

Hai kịch bản vận hành của giai đoạn hiện tại:

| Kịch bản         | order_type | order_channel | Ai đặt món | Thanh toán                | Gọi khách khi xong           |
| ---------------- | ---------- | ------------- | ---------- | ------------------------- | ---------------------------- |
| Take Away        | Take Away  | POS           | Nhân viên  | Quầy (Cash/QR thanh toán) | Gọi tên/số trên Status board |
| Dine In tại quầy | Dine In    | POS           | Nhân viên  | Quầy (Cash/QR thanh toán) | Thẻ bàn — phục vụ mang ra    |

**Lưu ý phân biệt quan trọng:** "QR" trong cột Thanh toán là **QR để thanh toán**
(VietQR qua SePay, khách quét bằng app ngân hàng ngay tại quầy) — khác hoàn toàn với
"kênh QR" (`order_channel = QR Web`) là khách **tự đặt món** qua QR, đang hoãn sang
mục 3b. Tích hợp SePay để sinh mã thanh toán vẫn cần làm ở giai đoạn hiện tại.

**Dine In tại quầy** dùng **thẻ bàn** (2026-11-23, thay thẻ rung vật lý: số thẻ/bàn có sẵn; tên kỹ thuật vẫn `MYPOS Buzzer` / field `buzzer`):
khách ngồi, đồ uống xong thì thu ngân được báo và mang ra đúng thẻ bàn. **Take Away không dùng thẻ** — gọi tên/số thứ tự.
Field Link `buzzer` trên `POS Invoice` **chỉ áp dụng khi `order_type = Dine In`**. Thẻ là tài nguyên dùng lại theo pool
(`Sẵn sàng ⇄ Đang dùng`), "Đang dùng" tính theo đơn còn giữ thẻ.

Quy tắc xuyên suốt (áp dụng cho cả 2 luồng hiện tại):

- **Payment-gated preparation**: `custom_kitchen_status` chỉ được set khi
  `POS Invoice.status == "Paid"`. Đơn chưa thanh toán không tồn tại ở khâu pha chế.
- Vòng đời `custom_kitchen_status`: (trống) → `Chưa làm` (ngay khi Paid) →
  `Đã làm` (barista bắt đầu) → `Đã hoàn thành` (barista xong) — độc lập hoàn toàn
  với field `status` gốc của POS Invoice.
- Sau khi bấm "Add Order" trên POS, hệ thống tự động điều hướng sang trang Orders
  và mở sẵn đúng đơn đó để thanh toán ngay — không bắt nhân viên tự tìm lại đơn.
- Trang "Table" cũ được thay bằng **Status board** dùng chung cho cả Take Away và
  Dine In: hiển thị Đang làm / Hoàn thành, kèm gọi tên/số (Take Away) hoặc thẻ bàn
  (Dine In) khi xong.
- **Mỗi thẻ bàn chỉ giữ cho một đơn chưa kết thúc, không dùng chung.** Thẻ được gán khi tạo đơn Draft (cashier chọn thẻ),
  chuyển `Đang dùng` khi đơn Paid + submit. "Đã làm" vẫn giữ thẻ (thu ngân có role POS CASHIER nhận toast + chấm đỏ ở "Pha chế", `roles.md` §7b).
  Thẻ về `Sẵn sàng` **ngay** khi đơn kết thúc (Đã hoàn thành / Khách không nhận / Không thực hiện được), hoặc đơn bị hủy (Draft → Cancelled,
  đơn đã submit → `on_cancel`). Không có bước nhả thẻ thủ công. Chi tiết: `.claude/rules/leescoffee_pos/pos_invoice_hooks.md` §2.2.
- **Phân quyền màn POS theo role** (MANAGER / CASHIER / KITCHEN: menu, tab Pha chế, bước chuyển):
  cấu hình duy nhất ở hằng `*_BY_ROLE` trong `api/pos_api.py`, chặn ở backend. Bảng quyền + tồn đọng:
  `.claude/rules/leescoffee_pos/roles.md` §7.
- **Tùy chọn món động** (`MYPOS Option Group`, thay đường/đá cứng; phụ thu topping cộng SAU CTKM qua dòng Taxes and Charges
  kiểu `Actual`, `options.md` §9): cấu hình do admin
  tạo trên Desk, không có dữ liệu mẫu trong code; lưu JSON `POS Invoice Item.options`. Quy tắc áp dụng,
  hướng dẫn admin: `.claude/rules/leescoffee_pos/options.md`.
- **Web đặt món QR cho khách** (`/order/<token>`, `order_channel = "QR"`, mã `MYPOS Order QR` theo Branch,
  token phiên HMAC, chỉ chuyển khoản SePay, không thẻ bàn, không đổi điểm khi chưa có OTP): API riêng
  `api/customer_order_api.py`, tách khỏi `pos_api.py`. Quy tắc + bảo mật: `.claude/rules/leescoffee_pos/order-qr.md`.
- **CTKM (Pricing Rule) tính theo tổng qty mỗi mã trong hóa đơn** (`_apply_rules_on_total_qty`), không cộng
  chéo giữa các mã. Không dùng `is_cumulative` (cộng qty qua các hóa đơn trước) hay `mixed_conditions`
  (cộng chéo các mã); không sửa Pricing Rule. Chi tiết: `options.md` §7.
- **Khách vãng lai theo POS Profile** (2026-11-24, đã test Pass): field `POS Profile.custom_walk_in_customer` do người cấu hình tự chọn
  (không patch / hook / seed nào tự điền, không tên Customer cố định). Chưa cấu hình → đơn không chọn khách bị chặn (lỗi tiếng Việt).
  Server trả cờ `is_walk_in`; giao diện không so tên Customer. Chi tiết: `.claude/rules/leescoffee_pos/pos_profile.md`.
- **Màn hình khách `/pos/customer`** (2026-11-24, đã test Pass, `d13b37c`): chỉ hiển thị, đăng nhập bằng tài khoản thu ngân (thiết bị
  riêng). Trạng thái theo user ở Redis cache (`customer_display_api.py`), realtime + poll 3 giây; tiền luôn do server tính. Banner từ
  DocType `MYPOS Banner` (theo POS Profile, trống = mọi profile, 5 giây đổi ảnh). Chi tiết: `.claude/rules/leescoffee_pos/customer_display.md`.
- **Trạng thái thanh toán `POS Invoice.payment_status`** (2026-11-25, đã test Pass, `1346dae`): tính ở MỘT nơi — hook
  `before_submit` → "Đã thanh toán" (mọi đường: tiền mặt, webhook, Desk, QR), hủy → "Hủy", sinh QR → "Đang chờ"; đơn trả hàng
  không đụng. API / webhook không tự ghi giá trị này. Chi tiết: `.claude/rules/leescoffee_pos/pos_invoice_hooks.md` §2.0.
- **Workspace Desk theo vai trò** (2026-11-25, đã test Pass, `8f2e389`): MYPOS Cashier / Kitchen / Manager / Admin, giới hạn bằng
  `Workspace.roles` (+ System Manager), Desktop Icon + Sidebar "MYPOS". Workspace cũ `leescoffee_pos` đã xóa (patch `v1_mypos_workspaces`).
  Chỉ đổi giao diện: module `Leescoffee POS`, app, route `/pos` giữ nguyên. Chi tiết: `.claude/rules/leescoffee_pos/workspace.md` §7.
  2026-11-26 (đã test Pass, `6cf87db`): bỏ shortcut Draft / Unserved Orders, bỏ nút Lọc nhanh list POS Invoice; Workspace Sidebar
  "Leescoffee POS" **rỗng có chủ đích** chặn Frappe v16.30 tự sinh sidebar theo module — **xóa khi chuyển sang module MYPOS**.
- **Màn theo dõi đơn cho khách `/pos/status`** (2026-11-27, đã test Pass, `c4ee619`): treo TV, chỉ đọc; "Đang chuẩn bị" (Chưa làm) /
  "Sẵn sàng nhận món" (Đã làm), cùng điều kiện đơn với màn Pha chế; tên gọi rút gọn ở server (từ cuối, không SĐT / tiền / món); dùng lại
  phiên bản thay đổi + realtime + lưới an toàn 60 giây. Tài khoản TV: POS KITCHEN riêng (role POS DISPLAY để sau). Chi tiết:
  `.claude/rules/leescoffee_pos/order_status.md`; treo TV: `.claude/docs/deploy.md` §4.
- **Giảm tải poll màn POS** (2026-11-25, giai đoạn 1 + 2 đã test Pass, `86b6cb2`): màn Pha chế / Orders / hàng chờ thu ngân / chọn thẻ bàn hỏi
  phiên bản thay đổi theo POS Profile (`get_pos_changes`, chỉ đọc Redis, 4 giây) và chỉ tải danh sách khi đổi. Code ghi POS Invoice bằng
  `set_value` / SQL phải gọi `change_feed.bump(pos_profile)`. Pha chế chỉ hiện đơn của POS Profile user thuộc về (tài khoản pha chế phải nằm
  trong Applicable for Users). Giai đoạn 3 (đã test Pass, `4fbb595`): sự kiện realtime `mypos_pos_changed` {p, v} phòng `all`; socket kết nối
  -> poll 30 giây, mất -> 4 giây (màn khách 3 giây). DEV mở site bằng `localhost:8001` (WSL2). Chi tiết: `.claude/rules/leescoffee_pos/realtime.md`;
  triển khai thật: `.claude/docs/deploy.md`.
