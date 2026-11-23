# Module Rules: POS Invoice Hooks & Buzzer Lifecycle

> Paths: `leescoffee_pos/leescoffee_pos/doctype/pos_invoice_hooks/`

## 1. Custom Fields on POS Invoice

| Field | Type | Purpose |
|-------|------|---------|
| `order_type` | Select: `Take Away` / `Dine In` | Loại đơn hàng |
| `order_channel` | Select: `POS` | Kênh đặt (hiện tại chỉ POS) |
| `custom_kitchen_status` | Select: `Chưa làm` / `Đã làm` / `Đã hoàn thành` / `Khách không nhận` / `Không thực hiện được` | Trạng thái pha chế (bộ lọc chuẩn) |
| `buzzer` | Link → `MYPOS Buzzer` | Thẻ bàn (chỉ Dine In; label Desk "MYPOS Buzzer", POS hiện "Thẻ bàn" / "Bàn #") |
| `payment_code` | Data | Mã thanh toán SePay |
| `payment_status` | Select | Trạng thái thanh toán |
| `transaction_ref` | Data | Mã tham chiếu giao dịch |
| `sepay_payment_log` | Small Text | JSON log webhook |
| `redeemed_points` | Int (read only) | Điểm Loyalty đã đổi; `on_submit` ghi Loyalty Point Entry âm qua `pos_api._record_redemption` |
| `custom_cancel_reason` | Small Text (read only, hiện khi docstatus 2) | Lý do hủy Draft, tiền tố Thủ công / Tự động (2026-11-23, `roles.md` §2c) |
| `custom_late_payment` | Check (bộ lọc chuẩn) | Có tiền chuyển khoản về sau khi đơn đã hủy (`sepay.md` §3) |
| `custom_late_payment_ref` | Data | Mã giao dịch tiền về sau hủy (phân cách dấu phẩy, chống ghi trùng) |

## 2. Lifecycle Rules

### 2.1 Kitchen Status (`custom_kitchen_status`)

- **Chỉ được set khi `status == "Paid"`** (kiểm tra trong `on_submit`).
- Vòng đời: `(trống)` → `Chưa làm` → `Đã làm` → `Đã hoàn thành`.
- **Trạng thái kết thúc có lý do (2026-11-20) — ĐÃ TEST PASS trên bench DEV (`2325990`; đơn giản hóa 2026-11-23, `0553fd2`)** — hằng ở MỘT nơi
  `doctype/pos_invoice_hooks/kitchen_status.py`: `Khách không nhận`, `Không thực hiện được` (thu ngân / quản lý qua `pos_api.resolve_open_order`,
  mỗi đơn một lý do). "Đã đóng ca chưa xử lý" và cờ `needs_review` đã bỏ (patch `v1_simplify_cancel_review` chuyển đơn cũ → "Không thực hiện được").
  - `KITCHEN_FLOW` (bước tiến của `set_kitchen_status`) không đổi; `KITCHEN_BLOCK_STATUSES` = Chưa làm, Đã làm (chặn đóng ca);
    `KITCHEN_TERMINAL_STATUSES` = Đã hoàn thành, Khách không nhận, Không thực hiện được (không giữ thẻ bàn, không chặn đóng ca).
  - Custom Field POS Invoice (read only, allow_on_submit): `kitchen_done_by/at` (Chưa làm→Đã làm), `kitchen_completed_by/at` (kết thúc),
    `kitchen_outcome_reason` (label "Lý do xử lý pha chế"). Dữ liệu cũ để trống.
  - `resolve_open_order(invoice_name, outcome, reason, note)`: CASHIER/MANAGER; đơn Paid (hoặc Consolidated — chỉ manager) đang rỗng / Chưa làm / Đã làm;
    lý do bắt buộc trừ Đã làm → Đã hoàn thành; ghi người/giờ, comment trên đơn.
  - `set_kitchen_status` trên đơn đã kết thúc → lỗi "đã kết thúc".
  - `shift_open_orders(pos_profile, period_start)` → `{drafts, unprepared, undelivered}` (đơn Paid của ca: cùng profile + giờ ghi sổ ≥ giờ
    mở ca, chưa gộp; trạng thái rỗng tính là Chưa làm) — dùng cho chặn đóng ca.
- `on_submit` tự động set `Chưa làm` khi Paid và chưa có kitchen status.
- **Sử dụng `doc.db_set()`** để update DB ngay trong transaction (tránh race condition).
- Dùng để khởi tạo vòng đời pha chế sau khi thanh toán thành công.

### 2.2 Thẻ bàn (MYPOS Buzzer) — Dine In only — ĐÃ TEST PASS trên bench DEV (`f2236b4`, `adcb92d`, `3736f85`, `4712d68`)

> 2026-11-23: "thẻ rung" vật lý đổi thành **thẻ bàn** (số thẻ/bàn có sẵn). Tên kỹ thuật giữ nguyên: DocType `MYPOS Buzzer`, field `buzzer`,
> `buzzer_number`, API `get_buzzers`, CSS `.pos-buzzer*`. **Desk dùng tên kỹ thuật** (link workspace "MYPOS Buzzer", label field POS Invoice
> "MYPOS Buzzer", `buzzer_number` "Số thẻ"); **POS và hóa đơn in dùng "Thẻ bàn" / "Bàn #"**.

**Quy tắc (Van, 2026-10-27, giữ nguyên): mỗi thẻ chỉ giữ cho MỘT đơn chưa kết thúc, không dùng chung.**

- **Take Away không dùng thẻ** — mọi logic thẻ chỉ chạy khi `order_type == "Dine In"`. Đơn QR không có thẻ.
- **"Đang dùng" tính theo ĐƠN CÒN GIỮ** (`pos_api._held_buzzers`, nguồn duy nhất cho `get_buzzers` và `_assign_buzzer`): tồn tại POS Invoice
  Dine In, `buzzer` = thẻ, `docstatus in (0, 1)`, `custom_kitchen_status` không thuộc `KITCHEN_TERMINAL_STATUSES`. Đơn Cancelled (docstatus 2) không giữ.
  Field `status` lưu trên thẻ (Sẵn sàng / Đang dùng) chỉ để hiện trên Desk; `get_buzzers` trả `status` tính lại theo đơn, `_assign_buzzer` không đọc
  field này → thẻ kẹt "Đang dùng" không bị khóa (patch `v1_table_card_cleanup` trả thẻ kẹt về Sẵn sàng).

| Bước | Nơi xử lý | Thẻ bàn |
|------|-----------|----------|
| 1. Tạo đơn Draft | `pos_api.create_draft_order` → `_assign_buzzer(profile, buzzer)` | Gán vào `POS Invoice.buzzer`; đang giữ |
| 2. Thanh toán (Paid + submit) | hook `on_submit` | field `status` → **Đang dùng** (đã "Đang dùng" → bỏ qua) |
| 3. Pha chế "Đã làm" | `set_kitchen_status` | **Vẫn giữ thẻ**; thu ngân nhận thông báo (`roles.md` §7b) |
| 4. Kết thúc (Đã hoàn thành / Khách không nhận / Không thực hiện được) | hook `on_update_after_submit` (save từ `set_kitchen_status` hoặc `kitchen_status.set_terminal`) | **Sẵn sàng ngay** |
| 4b. Kết thúc đơn đã gộp (Consolidated) | `pos_api._resolve_consolidated` → `PosInvoiceHooks.release_buzzer` | Sẵn sàng |
| 5. Hủy Draft | `order_cancel.cancel_draft` (Cancelled, không xóa) | field `status` chưa từng đổi; đơn docstatus 2 nên hết giữ |
| 6. Hủy đơn đã submit | hook `on_cancel` (mọi trạng thái pha chế, 2026-11-23) | Sẵn sàng |

- **Không có bước nhả thẻ thủ công** (2026-11-23): đã bỏ API `confirm_pickup`, nút "Xác nhận khách đã lấy", nút "Đã phục vụ".
- `_assign_buzzer` ném lỗi nếu thẻ không thuộc chi nhánh của POS Profile hoặc đang giữ cho đơn khác ("Thẻ bàn số … đang giữ cho đơn …").
- Kiểm tra: `.claude/docs/table_card_check.py` (`check_table_card(...)`).

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
- **`release_buzzer`** (đổi tên từ `confirm_pickup` 2026-11-23) là static method, không phải native lifecycle — chỉ `pos_api._resolve_consolidated` gọi (đơn đã gộp, không save được). `_free_buzzer_if_unheld` dùng chung cho `release_buzzer` và `on_cancel`.
- **`db_set()`** dùng trong `on_submit` để cập nhật `custom_kitchen_status` ngay trong transaction (tránh pending commit).
- **`frappe.get_all`** với `limit=1` và `fields=["name"]` để tối  hiệu suất khi kiểm tra đơn khác.
- **Import trong function** (`from ... import MYPOSBuzzer`) để tránh circular import.
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
  - `buzzer_number`: số thẻ bàn (null nếu Take Away)
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