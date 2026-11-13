# Module Rules: Tùy chọn món động (MYPOS Option) — KHÔNG phụ thu

> Paths: `leescoffee_pos/leescoffee_pos/doctype/mypos_option_group/` (DocType + `option_resolver.py`),
> `mypos_option_value/`, `mypos_option_target/` (bảng con), `api/pos_api.py` (`_normalize_items`,
> `get_order_detail`, `get_kitchen_orders`), `doctype/leescoffee_menu/leescoffee_menu.py`
> (`get_menu_with_items` thêm `option_groups`). Giai đoạn 1+2 (backend) làm 2026-11-13; giai đoạn 3 (UI) chưa làm.

## 1. Nguyên tắc

- Món có tùy chọn gì **do cấu hình quyết định**, backend là nguồn sự thật. Hệ thống sạch → món không có tùy chọn.
- **Không tạo dữ liệu mẫu** (Option Group/Value/Target) bằng code, patch hay fixtures. Admin tạo trên Desk.
- **Không phụ thu**: `extra_price` ẩn, luôn bỏ qua; `price` trong JSON luôn 0; giá dòng không đổi.
- DocType tiền tố `MYPOS`, module `Leescoffee POS`.

## 2. Mô hình dữ liệu

| DocType | Field |
|---|---|
| `MYPOS Option Group` (đặt tên `MYPOS-OPT-.####`) | `title`, `selection_type` (Chọn 1/Chọn nhiều), `required`, `sort_order`, `enabled`, `legacy_field` (none/sugar_level/ice_level), `values`, `targets` |
| `MYPOS Option Value` (bảng con) | `label` (không trùng trong nhóm), `is_default`, `sort_order`, `enabled`, `extra_price` (ẩn, mặc định 0) |
| `MYPOS Option Target` (bảng con) | `target_type` (Item Group/Item), `item_group` / `item`, `include_children` (mặc định 1), `exclude` |

- `validate()`: nhãn không trùng; Chọn 1 tối đa 1 mặc định; nhóm `required` không có mặc định → cảnh báo (không chặn).
- `on_update` / `on_trash` / `after_rename` → xóa cache cấu hình.
- Nhóm không có giá trị đang bật hoặc không có target → bỏ qua.
- Custom Field `POS Invoice Item-options` (Long Text, read only, sau `ice_level`): JSON
  `[{"group": "<tên nhóm>", "group_title": "<title lúc bán>", "value": "<nhãn>", "price": 0}]`.
- Cột cũ `sugar_level`, `ice_level` giữ nguyên để tương thích.

## 3. Quy tắc áp dụng (`option_resolver.resolve_option_groups`)

1. **Variant tính theo template**: mã template + Item Group của template. Target Item trỏ vào mã
   variant **không được hỗ trợ** (admin chọn mã template).
2. Trong một nhóm: lấy dòng target khớp **cụ thể nhất**: Item > Item Group sâu hơn > Item Group cha
   (so `lft` của cây Item Group). `include_children = 0` thì chỉ khớp đúng nhóm đó.
   **Cùng độ cụ thể thì dòng Loại trừ thắng.**
3. Giữa các nhóm: mọi nhóm khớp đều áp dụng, **trừ** hai nhóm trùng `title` hoặc trùng `legacy_field`
   (khác none) → chỉ giữ nhóm có target cụ thể hơn (hòa: `sort_order` nhỏ hơn, rồi tên).
4. Thứ tự trả về: `sort_order`, rồi tên nhóm; giá trị theo `sort_order`, rồi `idx`.

**Truy vấn & cache:** cấu hình nhóm (3 truy vấn) cache ở `frappe.cache` khóa `mypos_option_config`,
xóa khi lưu/xóa nhóm. Item / template / cây Item Group đọc mỗi lần (3 truy vấn gom cho cả danh sách),
không cache → đổi nhóm hàng có hiệu lực ngay.

## 4. API

- `get_menu_items`: mỗi món thêm `option_groups: [{name, title, selection_type, required,
  values: [{label, is_default}]}]` (không trả `extra_price`, không trả targets). Khóa cũ giữ nguyên.
- `preview_pricing`, `create_draft_order` (qua `_normalize_items`), mỗi dòng:
  - **Không có khóa `options`** (frontend cũ): hành vi cũ, `sugar`/`ice` mặc định 100, không ghi JSON.
  - **Có khóa `options`** `[{group, value}]` (`value` có thể là list cho Chọn nhiều): server kiểm tra:
    nhóm áp dụng cho món, giá trị thuộc nhóm và đang bật, Chọn 1 không nhiều giá trị; nhóm `required`
    không gửi → dùng mặc định, không có mặc định → lỗi tiếng Việt; nhóm không bắt buộc không gửi → không chọn gì.
    Ghi JSON. Nhóm có `legacy_field` → lấy số từ nhãn ghi vào cột cũ ("50%" → `50`); số không thuộc
    50/70/100 → **để trống cột cũ**, chỉ lưu JSON. Request gửi rõ `sugar`/`ice` (hoặc `sugar_level`/`ice_level`)
    thì vẫn lưu, nhưng `legacy_field` ghi đè.
  - Cùng món khác tổ hợp tùy chọn = các dòng khác nhau (frontend gộp theo khóa item + options).
- Giá: không cộng `extra_price`; kiểm tra giá Price List, CTKM, đổi điểm giữ nguyên.
- `get_order_detail`, `get_kitchen_orders`: mỗi món thêm `options` (đọc JSON; JSON rỗng mà cột cũ có giá trị
  → dựng từ cột cũ bằng hằng `LEGACY_OPTION_LABELS`, tạm thời, bỏ khi hết đơn cũ). `sugar_level`/`ice_level` vẫn trả.

## 5. Quyền

`MYPOS Option Group`: MANAGER R W C; CASHIER, KITCHEN R (patch `v1_create_pos_roles`). Bảng con không có
DocPerm riêng (Frappe xét theo DocType cha).

## 6. Hướng dẫn admin cấu hình (ví dụ — KHÔNG có trong code)

Desk → MYPOS Option Group → New:

- **Đường** (Chọn 1, Bắt buộc, `legacy_field = sugar_level`): giá trị `50%`, `70%`, `100%` (mặc định).
  Áp dụng: Item Group "Sản phẩm bán ra" (gồm nhóm con) + dòng **Loại trừ** "Bánh Ngọt", "Hàng Đóng Gói".
- **Đá** (Chọn 1, Bắt buộc, `legacy_field = ice_level`): `50%`, `70%`, `100%` (mặc định). Áp dụng như Đường.
- **Đường** riêng cho trà (vd. `0%`, `30%`, `50%`): tạo nhóm thứ hai cùng title "Đường", áp dụng "Trà & Trái Cây"
  → thay nhóm Đường chung cho trà (nhóm sâu hơn thắng). Giá trị ngoài 50/70/100 chỉ lưu JSON.
- **Topping** (Chọn nhiều, không bắt buộc, `legacy_field = none`): `Trân châu`, `Thạch`. Chưa có phụ thu.
- Món ngoại lệ trong nhóm bị loại trừ: thêm dòng target Item (mã **template** nếu món có size) → Item thắng nhóm.
- Món có size: gắn target vào **template**, không gắn vào variant.

## 7. Rủi ro / tồn đọng

- `get_menu_items` thêm ~3 truy vấn mỗi lần gọi (+ 3 khi cache trống).
- **CTKM theo số lượng**: cùng món khác tùy chọn tách dòng → Pricing Rule có thể xét qty từng dòng
  (2 + 2 ≠ 4). Script test có 2 ca; nếu mất ưu đãi: bật **Mixed Conditions** hoặc **Is Cumulative** trên
  Pricing Rule (cấu hình admin), hoặc task sau gộp qty theo item khi tính luật.
- Đóng ca: `options` nằm trên POS Invoice Item; Sales Invoice gộp không có field này (giống đường/đá cũ).
- Frontend cũ không gửi `options` → đi đường cũ; UI chưa hiển thị `option_groups` (giai đoạn 3).
- Phụ thu topping: xem `task_handoff.md` mục "Task sau: phụ thu topping".
