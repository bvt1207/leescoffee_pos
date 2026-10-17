# Module Rules: Leescoffee Menu / Menu Item — Price Logic

> Paths: `leescoffee_pos/leescoffee_pos/doctype/leescoffee_menu/` và `leescoffee_menu_item/`

## 1. DocType

- `Leescoffee Menu` (module "Leescoffee Pos"): `menu_name`, `price_list` (Link → Price List), `currency` (default VND), `items` (Table → Leescoffee Menu Item).
- `Leescoffee Menu Item` (child table): `item_code` (Link → Item), `item_name`, `item_type`, `price`, `currency`.

## 2. Price logic (shared between `get_price_for_item()` and `load_item_price()`)

1. **Fetch Item Price** by `item_code` + `price_list` + `selling=1` + `currency=VND`.
2. **Template vs Variant**:
   - Template = `has_variants = 1` AND `variant_of = ""` → không có giá, trả `None`.
   - Variant (`variant_of != ""`) → lấy giá theo chính `item_code` Variant.
3. **Item bị disable** → throw error.
4. **Hiệu lực**: `valid_from`/`valid_upto` NULL được coi là luôn hiệu lực. Chỉ loại bỏ nếu `valid_from > ngày hiện tại` hoặc `valid_upto < ngày hiện tại`. Dùng `getdate(nowdate())` để chuẩn hóa cả 2 về `datetime.date`.
5. **Không tìm thấy giá phù hợp** → trả `None` (không gán `0.0`).

## 3. Item type

- `is_stock_item = 1` → "Stock", còn lại → "Service". Không dùng `has_stock_field`.

## 4. validate() của Menu

- Tự động gọi `row.load_item_details(parent_doc=self)` cho từng dòng để đồng bộ `item_name`, `item_type`, `price` trước khi lưu.

## 5. get_parent_doc()

- Xử lý cả trường hợp `parent_doc` là weakref (callable) trước khi fallback `frappe.get_doc("Leescoffee Menu", self.parent)`.
