# Module Rules: Tùy chọn món động (MYPOS Option) — phụ thu cộng SAU CTKM

> Paths: `mypos/mypos/doctype/mypos_option_group/` (DocType + `option_resolver.py`),
> `mypos_option_value/`, `mypos_option_target/` (bảng con), `api/pos_api.py` (`_normalize_items`,
> `get_order_detail`, `get_kitchen_orders`), `doctype/mypos_menu/mypos_menu.py`
> (`get_menu_with_items` thêm `option_groups`). Giai đoạn 1+2 (backend) làm 2026-11-13, đã test Pass; giai đoạn 3 (UI) làm 2026-11-13, đã test Pass (`2f1d629`).

## 1. Nguyên tắc

- Món có tùy chọn gì **do cấu hình quyết định**, backend là nguồn sự thật. Hệ thống sạch → món không có tùy chọn.
- **Không tạo dữ liệu mẫu** (Option Group/Value/Target) bằng code, patch hay fixtures. Admin tạo trên Desk.
- **Phụ thu (2026-11-17, §9)**: `extra_price` của giá trị cộng SAU CTKM qua một dòng Taxes and Charges kiểu `Actual`;
  `rate` của món không đổi. Không có topping có giá → số liệu như trước.
- DocType tiền tố `MYPOS`, module `MYPOS`.

## 2. Mô hình dữ liệu

| DocType | Field |
|---|---|
| `MYPOS Option Group` (đặt tên `MYPOS-OPT-.####`) | `title`, `selection_type` (Chọn 1/Chọn nhiều), `required`, `sort_order`, `enabled`, `legacy_field` (none/sugar_level/ice_level), `values`, `targets` |
| `MYPOS Option Value` (bảng con) | `label` (không trùng trong nhóm), `is_default`, `sort_order`, `enabled`, `extra_price` ("Phụ thu", ≥ 0, mặc định 0) |
| `MYPOS Option Target` (bảng con) | `target_type` (Item Group/Item), `item_group` / `item`, `include_children` (mặc định 1), `exclude` |

- `validate()`: nhãn không trùng; Chọn 1 tối đa 1 mặc định; nhóm `required` không có mặc định → cảnh báo (không chặn).
- `on_update` / `on_trash` / `after_rename` → xóa cache cấu hình.
- Nhóm không có giá trị đang bật hoặc không có target → bỏ qua.
- Custom Field `POS Invoice Item-options` (Long Text, read only, sau `ice_level`): JSON
  `[{"group": "<tên nhóm>", "group_title": "<title lúc bán>", "value": "<nhãn>", "price": <phụ thu mỗi đơn vị lúc bán>}]`.
- Cột cũ `sugar_level`, `ice_level` giữ nguyên để tương thích. **Không có default** (fixture `default` trống) và **lựa chọn đầu là trống**
  (options `\n50\n70\n100`: Frappe tự gán lựa chọn đầu tiên cho Select không có default — `create_new.get_static_default_value`;
  thiếu dòng trống thì dòng mới nhận `50`) — chỉ được ghi khi request kiểu cũ
  (không khóa `options`), request gửi rõ sugar/ice, hoặc nhóm có `legacy_field`.

## 3. Quy tắc áp dụng (`option_resolver.resolve_option_groups`)

1. **Variant tính theo template**: mã template + Item Group của template. Target Item trỏ vào mã
   variant **không được hỗ trợ** (admin chọn mã template).
2. Trong một nhóm: lấy dòng target khớp **cụ thể nhất**: Item > Item Group sâu hơn > Item Group cha
   (so `lft` của cây Item Group). `include_children = 0` thì chỉ khớp đúng nhóm đó.
   **Cùng độ cụ thể thì dòng Loại trừ thắng.**
3. Giữa các nhóm: mọi nhóm khớp đều áp dụng, **trừ** hai nhóm trùng `title` hoặc trùng `legacy_field`
   (khác none) → chỉ giữ nhóm có target cụ thể hơn (hòa: `sort_order` nhỏ hơn, rồi tên).
4. Thứ tự trả về: `sort_order`, rồi tên nhóm; giá trị theo `sort_order`, rồi `idx`.

**Truy vấn & cache:** cấu hình nhóm (3 truy vấn) cache ở `frappe.cache` khóa `mypos_option_config_v2` (v2 có `extra_price`),
xóa khi lưu/xóa nhóm. Item / template / cây Item Group đọc mỗi lần (3 truy vấn gom cho cả danh sách),
không cache → đổi nhóm hàng có hiệu lực ngay.

## 4. API

- `get_menu_items`: mỗi món thêm `option_groups: [{name, title, selection_type, required,
  values: [{label, is_default, extra_price}]}]` (không trả targets). Khóa cũ giữ nguyên.
- `preview_pricing`, `create_draft_order` (qua `_normalize_items`), mỗi dòng:
  - **Không có khóa `options`** (frontend cũ): hành vi cũ, `sugar`/`ice` mặc định 100, không ghi JSON.
  - **Có khóa `options`** `[{group, value}]` (`value` có thể là list cho Chọn nhiều): server kiểm tra:
    nhóm áp dụng cho món, giá trị thuộc nhóm và đang bật, Chọn 1 không nhiều giá trị; nhóm `required`
    không gửi → dùng mặc định, không có mặc định → lỗi tiếng Việt; nhóm không bắt buộc không gửi → không chọn gì.
    Ghi JSON. Nhóm có `legacy_field` → lấy số từ nhãn ghi vào cột cũ ("50%" → `50`); số không thuộc
    50/70/100 → **để trống cột cũ**, chỉ lưu JSON. Request gửi rõ `sugar`/`ice` (hoặc `sugar_level`/`ice_level`)
    thì vẫn lưu, nhưng `legacy_field` ghi đè.
  - Cùng món khác tổ hợp tùy chọn = các dòng khác nhau (frontend gộp theo khóa item + options).
- Giá món: kiểm tra giá Price List, CTKM giữ nguyên; phụ thu cộng sau (§9).
- `get_order_detail`, `get_kitchen_orders`, `customer_order_api._orders_payload` (`get_my_orders`, `get_order`): mỗi món thêm
  `options` qua **một** hàm `option_resolver.read_line_options` (2026-11-20): cột `options` **NULL/rỗng** (đơn cũ chưa từng ghi JSON)
  mà cột cũ có giá trị → dựng từ cột cũ bằng hằng `LEGACY_OPTION_LABELS` (tạm thời, bỏ khi hết đơn cũ); **`'[]'` = đã xử lý,
  không có tùy chọn → `[]`** (không dựng từ cột cũ); JSON hỏng → `[]`. Frontend chỉ hiển thị `options` server trả. `sugar_level`/`ice_level` vẫn trả.

## 5. Quyền

`MYPOS Option Group`: MANAGER R W C; CASHIER, KITCHEN R (`mypos/setup/roles.py`). Bảng con không có
DocPerm riêng (Frappe xét theo DocType cha).

## 6. Hướng dẫn admin cấu hình (ví dụ — KHÔNG có trong code)

Desk → MYPOS Option Group → New:

- **Đường** (Chọn 1, Bắt buộc, `legacy_field = sugar_level`): giá trị `50%`, `70%`, `100%` (mặc định).
  Áp dụng: Item Group "Sản phẩm bán ra" (gồm nhóm con) + dòng **Loại trừ** "Bánh Ngọt", "Hàng Đóng Gói".
- **Đá** (Chọn 1, Bắt buộc, `legacy_field = ice_level`): `50%`, `70%`, `100%` (mặc định). Áp dụng như Đường.
- **Đường** riêng cho trà (vd. `0%`, `30%`, `50%`): tạo nhóm thứ hai cùng title "Đường", áp dụng "Trà & Trái Cây"
  → thay nhóm Đường chung cho trà (nhóm sâu hơn thắng). Giá trị ngoài 50/70/100 chỉ lưu JSON.
- **Topping** (Chọn nhiều, không bắt buộc, `legacy_field = none`): `Trân châu` (Phụ thu 10.000), `Thạch` (5.000).
- Món ngoại lệ trong nhóm bị loại trừ: thêm dòng target Item (mã **template** nếu món có size) → Item thắng nhóm.
- Món có size: gắn target vào **template**, không gắn vào variant.

## 7. Rủi ro / tồn đọng

- `get_menu_items` thêm ~3 truy vấn mỗi lần gọi (+ 3 khi cache trống).
- **CTKM theo số lượng — ĐÃ XỬ LÝ (2026-11-13):** ERPNext xét qty của Pricing Rule theo từng dòng, nên
  2 + 2 ly cùng mã (khác tùy chọn) chỉ được mức qty 2. `pos_api._apply_rules_on_total_qty` (gọi trong
  `_build_invoice`, dùng chung cho `preview_pricing` và `create_draft_order`): mã có ≥ 2 dòng → dựng hóa đơn
  tạm trong bộ nhớ, mỗi mã 1 dòng qty = tổng, để ERPNext chọn luật, rồi chép `pricing_rules`,
  `discount_percentage`, `discount_amount`, `rate` (+ margin) sang mọi dòng thật cùng mã.
  - Quy tắc: **CTKM tính theo tổng qty mỗi mã trong hóa đơn**; hai mã khác nhau không cộng chéo.
  - **Không dùng `is_cumulative`**: ERPNext cộng dồn qty qua các hóa đơn trước (đã thử trên bench: qty 1
    cũng được giảm 10%). **Không dùng `mixed_conditions`**: cộng chéo giữa các mã trong cùng luật. Không sửa Pricing Rule.
  - Luật tặng sản phẩm (`price_or_product_discount = Product`) **không gộp**: giữ theo từng dòng, ghi Error Log.
  - Giá mỗi đơn vị sau giảm giống nhau trên mọi dòng cùng mã → tổng không lệch so với 1 dòng qty tổng.
  - Khi insert/save/submit, ERPNext chạy lại `set_missing_values(for_validate=True)`;
    dùng lại luật đã ghi trong `pricing_rules` — **đã test Pass trên bench (`5b17b6c`)**: tổng hóa đơn thật (sau tạo và sau `pay_cash`) khớp preview ở mọi ca.
- Đóng ca: `options` nằm trên POS Invoice Item; Sales Invoice gộp không có field này (giống đường/đá cũ).
- Frontend cũ (trước giai đoạn 3) không gửi `options` → đi đường cũ.
- Phụ thu topping: backend làm 2026-11-17 (§9); UI (chip "+giá", giỏ, hóa đơn) là giai đoạn 2.

## 8. Frontend (giai đoạn 3, chỉ `pos/src`)

- `lib/options.ts` (không hardcode tên nhóm/giá trị): `defaultOptions` (is_default; Chọn 1 lấy 1),
  `normalizeOptions` (thứ tự cấu hình, bỏ trùng), `optionsKey`, `toggleOption`, `missingRequired`,
  `formatOptions` / `optionParts` (gom theo `group_title`: "Đường 70% · Đá 50% · Topping Trân châu, Thạch"),
  `formatCartOptions`.
- `CartLine` lưu `options` + `option_groups` của món (variant dùng `option_groups` của template, vì server
  tính ở cấp món). Khóa giỏ = `item_code` + options chuẩn hóa.
- `MenuGrid.addSize`: khởi tạo options mặc định khi thêm món (1 size hoặc qua SizeModal).
- `CartPanel`: chip theo nhóm, thu gọn/mở, trạng thái thiếu bắt buộc. `POS.tsx`: gửi `options` cho preview +
  tạo đơn (luôn gửi khóa `options`, kể cả rỗng → server đi đường mới), chặn Tạo đơn khi thiếu nhóm bắt buộc.
- Hiển thị: Orders (`pos-detail__opts`), Kitchen (chip `pos-chip-opt` mỗi nhóm), ReceiptModal (hóa đơn + phiếu
  pha chế), CupLabels (tem ly, `Cup.opts`) — đều từ `options` server trả; món không có tùy chọn không in dòng.
- Đã bỏ: `LEVELS`, `ICE_SUGAR`, `changeIceSugar`, `optsLabel`, CSS `.pos-segmented--sm`, `.pos-cart-line__option*`.

## 9. Phụ thu tùy chọn món (topping) — backend 2026-11-17, đã test Pass (`c97f685`, gồm đóng ca)

**Quy tắc:** giá cuối dòng = `rate` sau Pricing Rule + Σ `extra_price` các giá trị đã chọn (× qty dòng).
Phụ thu **không** bị CTKM giảm, **không** đếm vào qty của luật, **không** cộng cho dòng tặng (`is_free_item`).
Topping là `MYPOS Option Value` có `extra_price` — không tạo Item, Price List hay dòng hóa đơn phụ.

**Cách lưu (phương án C, Van duyệt):** `pos_api._apply_option_surcharge(invoice, profile)` (cuối `_build_invoice`,
dùng chung `preview_pricing`, `create_draft_order`, `customer_order_api`) thêm/cập nhật **đúng một** dòng
`Taxes and Charges`: `charge_type = "Actual"`, `description = "Phụ thu tùy chọn món"` (`SURCHARGE_DESCRIPTION`,
dùng để nhận diện), `tax_amount` = tổng phụ thu, `account_head` = `POS Profile.income_account` → `Company.default_income_account`
(thiếu cả hai → lỗi rõ ràng, chỉ khi có phụ thu > 0). Idempotent: gọi nhiều lần không nhân đôi; tổng 0 → xóa dòng cũ.
- Vì sao không cộng vào `rate`: khi insert/save/submit ERPNext chạy lại `set_missing_values` + `calculate_taxes_and_totals`,
  dòng có luật % bị tính lại `rate = price_list_rate × (1 − %)` → mất phụ thu [Inference, đọc mã ERPNext]. Margin cũng sai
  (CTKM giảm cả phụ thu). Dòng `Actual` giữ nguyên số tiền khi save/submit; khi đóng ca được gộp sang Sales Invoice theo tài khoản.
- `price` trong JSON `options` = phụ thu **mỗi đơn vị** lấy từ DB lúc bán (snapshot, không tin client). Đổi giá topping
  sau khi bán không đổi đơn cũ.
- Đổi điểm (giảm trên Grand Total) tính trên tổng sau luật + phụ thu; tổng sau đổi điểm không được âm.
- `preview_pricing` trả `total_surcharge`; `get_order_detail` trả `total_surcharge` (từ dòng Actual) + `options[].price`;
  `get_kitchen_orders`, `get_my_orders` trả `options[].price`.

**Lưu ý thuế / báo cáo:**
- Dòng `Actual` **không chịu thuế %** của mẫu thuế (đứng sau các dòng % "On Net Total"). Site có mẫu thuế VAT tính trên
  doanh thu cần lưu ý: phụ thu đang **không** bị tính VAT — nếu cần, tạo dòng VAT riêng "On Previous Row Amount" hoặc
  xử lý kế toán khi đóng sổ.
- Báo cáo doanh số theo món **không** gồm phụ thu (nằm ở dòng phí riêng, tài khoản doanh thu đã chọn).

**Kiểm tra:** `mypos/selfcheck/surcharge_check.py` (`check_option_surcharge(...)`): số cũ không topping, topping 49.000 /
180.400 / 170.400 (2 dòng vẫn giảm 10%), chọn nhiều, từ chối giá trị tắt/nhóm không áp dụng, idempotent, đổi điểm,
webhook đơn QR, đổi giá sau bán, hủy Draft + xóa như job dọn đơn QR, mẫu thuế, thiếu tài khoản, mua tặng (tùy chọn).
Đóng ca: kiểm tra tay (checklist trong báo cáo).

### 9b. UI phụ thu (giai đoạn 2, `pos/src` + `pos/src/order`) — 2026-11-17, đã test Pass (`cabdabe`)

- `lib/options.ts`: `valueSurcharge`, `cartUnitSurcharge` (ước tính từ `extra_price` của menu, chỉ hiển thị),
  `lineUnitSurcharge` (từ `price` server lưu), `plusPrice` ("+10.000"); `formatOptions` / `optionParts` /
  `formatCartOptions` có tham số `withPrice` (mặc định không kèm giá).
- Chip: giá trị có phụ thu hiện "+giá" (`.pos-optchip__price` ở `/pos`, `.qo-chip__price` ở `/order`).
- Giỏ (`CartPanel`, `CartSheet`): giá dòng = (giá sau CTKM từ preview, hoặc giá món) + phụ thu × qty; tóm tắt tùy chọn kèm giá;
  dòng "Phụ thu topping +X" từ `preview.total_surcharge`; tổng tạm khi chưa có preview đã cộng phụ thu. `ItemSheet` hiện
  giá gồm topping đang chọn. Không thêm request: khóa debounce preview đã gồm `options`.
- Đơn đã tạo: `Orders` (chi tiết) + `ReceiptModal` (hóa đơn khách): tùy chọn kèm giá, giá dòng gồm phụ thu, dòng
  "Gồm phụ thu topping" (từ `total_surcharge`, chỉ thông tin — giá dòng đã gồm). `MyOrdersPanel`: tùy chọn kèm giá.
  `Kitchen`, `CupLabels`, phiếu pha chế: chỉ tên tùy chọn, không giá.
