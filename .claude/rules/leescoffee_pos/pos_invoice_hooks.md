# Module Rules: POS Invoice Hooks & Buzzer Lifecycle

> Paths: `leescoffee_pos/leescoffee_pos/doctype/pos_invoice_hooks/`

## 1. Custom Fields on POS Invoice

| Field | Type | Purpose |
|-------|------|---------|
| `order_type` | Select: `Take Away` / `Dine In` | Loại đơn hàng |
| `order_channel` | Select: `POS` | Kênh đặt (hiện tại chỉ POS) |
| `custom_kitchen_status` | Select: `Chưa làm` / `Đã làm` / `Đã hoàn thành` | Trạng thái pha chế |
| `buzzer` | Link → `Leescoffee Buzzer` | Thẻ rung (chỉ Dine In) |
| `payment_code` | Data | Mã thanh toán SePay |
| `payment_status` | Select | Trạng thái thanh toán |
| `transaction_ref` | Data | Mã tham chiếu giao dịch |
| `sepay_payment_log` | Small Text | JSON log webhook |

## 2. Lifecycle Rules

### 2.1 Kitchen Status (`custom_kitchen_status`)

- **Chỉ được set khi `status == "Paid"`** (kiểm tra trong `on_submit`).
- Vòng đời: `(trống)` → `Chưa làm` → `Đã làm` → `Đã hoàn thành`.
- `on_submit` tự động set `Chưa làm` khi Paid và chưa có kitchen status.
- **Sử dụng `doc.db_set()`** để update DB ngay trong transaction (tránh race condition).
- Dùng để khởi tạo vòng đời pha chế sau khi thanh toán thành công.

### 2.2 Buzzer Lifecycle (Dine In only)

**Quy tắc (quyết định của Van, 2026-10-27): mỗi thẻ chỉ giữ cho MỘT đơn chưa hoàn thành, không dùng chung.**

- **Take Away không tác động đến Buzzer** — mọi logic buzzer chỉ chạy khi `order_type == "Dine In"`.
- **Buzzer pool**: `Sẵn sàng` ⇄ `Đang dùng`, không có trạng thái Occupied cố định.
- **"Đang giữ"** = tồn tại POS Invoice `order_type = Dine In`, `buzzer` = thẻ đó,
  `docstatus in (0, 1)`, `custom_kitchen_status != "Đã hoàn thành"` (tính cả đơn Draft chưa thanh toán).
  Thẻ bị giữ thì không gán được cho đơn khác, kể cả khi `status` của thẻ vẫn là `Sẵn sàng`.

| Bước | Nơi xử lý | Thẻ rung |
|------|-----------|----------|
| 1. Tạo đơn Draft | `api/pos_api.py::create_draft_order` → `_assign_buzzer(profile, buzzer)` | **Gán** vào `POS Invoice.buzzer`. `status` thẻ vẫn `Sẵn sàng`, nhưng đã "đang giữ" |
| 2. Thanh toán (Paid + submit) | hook `on_submit` (sau `pay_cash` hoặc webhook SePay) | `Sẵn sàng` → **`Đang dùng`** |
| 3a. Pha chế xong | hook `on_update_after_submit` khi `custom_kitchen_status = "Đã hoàn thành"` (vd. `set_kitchen_status`) | `Đang dùng` → **`Sẵn sàng`** |
| 3b. Hủy đơn Draft | `api/pos_api.py::cancel_draft_order` (xóa hẳn đơn) | `status` chưa từng đổi; đơn bị xóa nên **hết "đang giữ"** → thẻ trống lại |

Chi tiết từng bước:

- **Bước 1 — `_assign_buzzer`**: cashier chọn thẻ qua `BuzzerPicker` (API `get_buzzers`
  trả `available`, `used_by`). Dine In bắt buộc có `buzzer`. Ném lỗi nếu thẻ không thuộc
  chi nhánh của POS Profile, `status != "Sẵn sàng"`, hoặc đang bị đơn khác giữ.
- **Bước 2 — `on_submit`**: thẻ `Sẵn sàng` → `Đang dùng`. Nếu thẻ đã `Đang dùng` → hiện
  code **bỏ qua, không ném lỗi** (chốt chặn dùng chung nằm ở bước 1). Trạng thái khác → ném lỗi.
- **Bước 3a**: chỉ reset khi không còn đơn Paid khác cùng thẻ chưa hoàn thành (§2.3).
- **Các đường reset khác vẫn có trong code** (cùng kiểm tra §2.3):
  - `confirm_pickup`: nhân viên xác nhận khách lấy món (kitchen status = `Đã hoàn thành`).
  - `on_cancel`: đơn **đã submit** bị cancel **và chưa bắt đầu làm** (`custom_kitchen_status` là None, "", hoặc `Chưa làm`).

> Lưu ý lệch với CLAUDE.md §3: CLAUDE.md ghi reset buzzer khi nhân viên xác nhận khách
> đã nhận món, "không tự động reset ngay khi barista đánh dấu xong". Code hiện tại
> reset ngay ở bước 3a, theo quy tắc mới ở trên. `confirm_pickup` thường không còn gì
> để reset. Chưa sửa CLAUDE.md §3; chờ Van quyết.

### 2.3 Kiểm tra đơn khác trước khi reset buzzer (phòng thủ)

Vì thẻ không dùng chung, bình thường sẽ không có đơn khác giữ cùng thẻ. Kiểm tra dưới đây
được giữ làm chốt an toàn (dữ liệu cũ, sửa tay trên Desk). Trước khi reset buzzer về `Sẵn sàng`, hệ thống kiểm tra:

```sql
SELECT 1 FROM `tabPOS Invoice` 
WHERE name != current_invoice_name
  AND docstatus = 1 
  AND status = 'Paid' 
  AND order_type = 'Dine In' 
  AND buzzer = current_buzzer
  AND custom_kitchen_status != 'Đã hoàn thành'
LIMIT 1
```

- **Nếu tìm thấy** (có đơn khác chưa hoàn thành): **Không thay đổi buzzer** (giữ nguyên trạng thái hiện tại).
- **Nếu không tìm thấy** (không có đơn khác cần buzzer): Cho phép thay đổi trạng thái buzzer.

## 3. Code Conventions

- **Native lifecycle methods** (`on_submit`, `before_save`, `on_update_after_submit`, `on_cancel`) viết trong class `PosInvoiceHooks`, delegate từ module-level wrappers.
- **`confirm_pickup`** là static method, không phải native lifecycle — gọi thủ công từ UI/API.
- **`db_set()`** dùng trong `on_submit` để cập nhật `custom_kitchen_status` ngay trong transaction (tránh pending commit).
- **`frappe.get_all`** với `limit=1` và `fields=["name"]` để tối  hiệu suất khi kiểm tra đơn khác.
- **Import trong function** (`from ... import LeescoffeeBuzzer`) để tránh circular import.
- **`ignore_permissions=True`** khi save buzzer (buzzer update từ hook, không cần permission check).
- **`method=None`** trong tất cả static methods để tương thích với Frappe hook system.

## 4. Status Board API

`get_status_board_orders()` (whitelisted):
- Trả về các POS Invoice đã submit (`docstatus=1`), Paid (`status="Paid"`), có `custom_kitchen_status` khác rỗng.
- Sắp xếp `order_by="creation asc"` (FIFO - đơn cũ nhất trước).
- Fields trả về:
  - `invoice_name`: tên POS Invoice
  - `customer_name`: tên khách hàng (lấy từ Customer.customer_name)
  - `order_type`: Take Away / Dine In
  - `kitchen_status`: trạng thái bếp (Chưa làm / Đã làm / Đã hoàn thành)
  - `buzzer_number`: số thẻ rung (null nếu Take Away)
  - `last_updated`: thời gian tạo invoice
- Không tạo DocType/Custom Field mới — tái sử dụng các field hiện có.

## 5. Hooks Registration

```python
doc_events = {
    "POS Invoice": {
        "on_submit": "leescoffee_pos.leescoffee_pos.doctype.pos_invoice_hooks.pos_invoice_hooks.on_submit",
        "before_save": "leescoffee_pos.leescoffee_pos.doctype.pos_invoice_hooks.pos_invoice_hooks.before_save",
        "on_update_after_submit": "leescoffee_pos.leescoffee_pos.doctype.pos_invoice_hooks.pos_invoice_hooks.on_update_after_submit",
        "on_cancel": "leescoffee_pos.leescoffee_pos.doctype.pos_invoice_hooks.pos_invoice_hooks.on_cancel",
    },
}
```