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

- **Take Away không tác động đến Buzzer** — mọi logic buzzer chỉ chạy khi `order_type == "Dine In"`.
- **Buzzer pool**: `Sẵn sàng` ⇄ `Đang dùng`, không có trạng thái Occupied cố định.
- **Khi Paid + submit**:
  - Nếu buzzer có trạng thái `Sẵn sàng` → chuyển sang `Đang dùng` và gán cho đơn.
  - Nếu buzzer đã ở trạng thái `Đang dùng` → **giữ nguyên** (cho phép chung buzzer giữa các đơn nếu cần).
  - Nếu buzzer ở trạng thái khác → **ném lỗi** (trạng thái không mong đợi).
- **Khi `custom_kitchen_status = "Đã hoàn thành"`**: 
  - Kiểm tra xem còn đơn Dine In nào khác:
    - Cùng buzzer
    - Chưa hoàn thành (`custom_kitchen_status != "Đã hoàn thành"`)
    - Đã thanh toán và submit (`status = "Paid"`, `docstatus = 1`)
  - **Chỉ reset buzzer về `Sẵn sàng` khi KHÔNG còn đơn nào khác** đáp ứng điều kiện trên.
- **Reset conditions** (cùng logic kiểm tra đơn khác):
  - `on_update_after_submit`: khi kitchen status chuyển sang `Đã hoàn thành`.
  - `confirm_pickup`: khi nhân viên xác nhận khách lấy món (kitchen status = `Đã hoàn thành`).
  - `on_cancel`: khi đơn bị hủy **và chưa bắt đầu làm** (`custom_kitchen_status` là None, "", hoặc `Chưa làm`).

### 2.3 Shared Buzzer Validation Logic

Trước khi thay đổi trạng thái buzzer (từ `Sẵn sàng` sang `Đang dùng` hoặc từ `Đang dùng` sang `Sẵn sàng`), hệ thống **luôn kiểm tra**:

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