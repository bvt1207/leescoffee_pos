# Code Standards — Leescoffee POS

> Tự động tải bởi Claude Code mỗi phiên làm việc. Xem CLAUDE.md mục 5.

## 1. Naming convention

- **DocType name**: Title Case (`Leescoffee Menu`)
- **Fieldname**: snake_case (`order_type`, `price_list`)
- **Module**: `Leescoffee Pos` (viết hoa "Pos", được viết tắt của "Point of Sale") cho DocType mới.
  Lệch đã biết: `modules.txt` + Workspace JSON dùng `Leescoffee POS` — giữ nguyên, xem CLAUDE.md §5.
- **Import path**: luôn viết đủ `leescoffee_pos.leescoffee_pos.<path>`, không rút gọn thành 1 cấp.

## 2. DocType JSON checklist

Mỗi file JSON DocType mới/sửa **bắt buộc** kiểm tra:

1. **Có `"doctype": "DocType"`** ở gốc file — thiếu dòng này gây lỗi `KeyError: 'doctype'` khi chạy `bench migrate`.
2. **fieldtype đúng casing chuẩn Frappe**: `Section Break`, `Link`, `Data`, `Check`, `Select`, `Password`, `Attach Image`, `Small Text`, `Currency`, `Int`, `Table`, `Read Only` ...
3. **fieldtype `Table` (child table)**: phải có `options` trỏ đến DocType con và DocType con phải có `istable: 1`.

## 3. Native lifecycle vs doc_events

- **Native lifecycle method** (`validate`, `before_save`, `on_update`, `on_submit`, ...) viết trực tiếp trong class kế thừa `Document` → Frappe tự động gọi. **KHÔNG đăng ký lại trong `hooks.py -> doc_events`**.
- **Custom cross-cutting logic** (như POS Invoice hooks) → dùng `doc_events` trong `hooks.py`.

## 4. import path convention

```
leescoffee_pos.leescoffee_pos.doctype.<doctype>.<file>.<function/class>
```

Ví dụ đúng:
```
leescoffee_pos.leescoffee_pos.doctype.pos_invoice_hooks.pos_invoice_hooks.on_submit
```

Không viết tắt 1 cấp:
```
❌ leescoffee_pos.doctype.pos_invoice_hooks.pos_invoice_hooks.on_submit
```

## 5. File organization

| Loại nội dung | Vị trí |
|---------------|--------|
| DocType mới (JSON + Python) | `leescoffee_pos/leescoffee_pos/doctype/<doctype>/` |
| Hooks chung cho core doctype | `leescoffee_pos/leescoffee_pos/doctype/<hook_doctype>/` |
| Helper logic (get_config, ...) | `leescoffee_pos/leescoffee_pos/doctype/branch_config/` |
| Whitelisted API | Trong thư mục module tương ứng (`doctype/<module>/<module>.py`) |
