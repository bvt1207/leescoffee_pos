# Code Standards — MYPOS

> Quy ước code của app. `CLAUDE.md` ở gốc app trỏ tới file này.

## 1. Naming convention

- **DocType name**: Title Case (`MYPOS Menu`)
- **Fieldname**: snake_case (`order_type`, `price_list`)
- **Module**: `MYPOS` cho mọi DocType/Workspace — chữ `module` của mọi DocType/Workspace phải **khớp chính xác** `MYPOS` (như `modules.txt`, Module Def). Lệch chữ → user không phải Administrator bị PermissionError khi vào các workspace MYPOS (`/desk/mypos-*`), vì `allowed_modules` lấy từ `module` của các DocType user có quyền Read.
- **Import path**: luôn viết đủ `mypos.mypos.<path>`, không rút gọn thành 1 cấp.

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
mypos.mypos.doctype.<doctype>.<file>.<function/class>
```

Ví dụ đúng:
```
mypos.mypos.doctype.pos_invoice_hooks.pos_invoice_hooks.on_submit
```

Không viết tắt 1 cấp:
```
❌ mypos.doctype.pos_invoice_hooks.pos_invoice_hooks.on_submit
```

## 5. File organization

| Loại nội dung | Vị trí |
|---------------|--------|
| DocType mới (JSON + Python) | `mypos/mypos/doctype/<doctype>/` |
| Hooks chung cho core doctype | `mypos/mypos/doctype/<hook_doctype>/` |
| Helper logic (get_config, ...) | `mypos/mypos/doctype/branch_config/` |
| Whitelisted API | Trong thư mục module tương ứng (`doctype/<module>/<module>.py`) |
