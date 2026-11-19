# Module Rules: MYPOS Menu / Menu Item — Price Logic

> Paths: `leescoffee_pos/leescoffee_pos/doctype/mypos_menu/` và `mypos_menu_item/`
> Đổi tên 2026-11-15: `Leescoffee Menu` / `Leescoffee Menu Item` / `Leescoffee Buzzer` → `MYPOS Menu` / `MYPOS Menu Item` /
> `MYPOS Buzzer` (patch `patches/v1_rename_mypos_doctypes.py`, [pre_model_sync], `frappe.rename_doc` + SQL sửa phần sót;
> có cả tên cũ lẫn mới → dừng, không xóa gì). Module vẫn `Leescoffee POS`. Kiểm tra: `.claude/docs/mypos_rename_check.py`.

## 1. DocType

- `MYPOS Menu` (module "Leescoffee POS"): `menu_name`, `price_list` (Link → Price List), `currency` (default VND), `items` (Table → MYPOS Menu Item).
- `MYPOS Menu Item` (child table): `item_code` (Link → Item), `item_name`, `item_type`, `price`, `currency`.

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

- Xử lý cả trường hợp `parent_doc` là weakref (callable) trước khi fallback `frappe.get_doc("MYPOS Menu", self.parent)`.

## 6. Payload `get_menu_items` cho lưới món POS

- Mỗi món: `{template, name, image, sizes: [{label, item_code, rate}], option_groups, item_group}`.
- `item_group` (thêm 2026-11-19): Item Group của mã trên dòng `MYPOS Menu Item` (template → nhóm của template), lấy cùng truy vấn
  Item đã có (không thêm truy vấn). `None` nếu Item không có nhóm.
- Web khách `/order` **không** nhận `item_group`: `customer_order_api._public_menu` chỉ chép khóa đã liệt kê.

## 7. Hướng dẫn admin: Item Group và ảnh món (dữ liệu demo nhập qua Desk, không có trong code)

- **Tab nhóm ở /pos** lấy từ **Item Group** của từng món (Item → trường Item Group). Món có size: đặt nhóm trên **template**.
- Thứ tự tab = thứ tự món đầu tiên của nhóm trong `MYPOS Menu` (kéo thả dòng món trong menu để sắp lại). "Tất cả" luôn đầu,
  "Khác" (món chưa có nhóm) luôn cuối. Chỉ có 1 nhóm → thanh tab ẩn.
- Nên dùng nhóm lá ngắn gọn (vd. tên loại đồ uống/bánh) thay vì nhóm gốc "All Item Groups" hay nhóm chung chung.
- **Ảnh món** (Item → Image): ảnh **vuông 1:1**, **nền sáng đồng nhất** cho mọi món, món nằm giữa, ≥ 400×400px, dung lượng nhỏ
  (≤ 200 KB, JPG/WebP). Thẻ món cắt ảnh theo khung vuông (`object-fit: cover`) — ảnh khác tỷ lệ sẽ bị cắt mép.
- Ảnh phải là file **public** (bỏ chọn "Is Private" khi tải lên); ảnh private không hiện cho khách ở web `/order`.
- Món không có ảnh hiển thị chữ cái đầu trên nền trung tính.
