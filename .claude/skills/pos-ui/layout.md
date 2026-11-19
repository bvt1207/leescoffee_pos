# Layout & Component — Leescoffee POS

> Nguồn: `.claude/skills/pos-ui/states.md` (component patterns, API mapping, checklist) + ảnh tham khảo trong `.claude/docs/reference/`:
> - `ury-pos.png` — bố cục trang POS chính
> - `ury-orders.png` — danh sách đơn và chi tiết đơn
> - `ury-orders-tabphache.png` — thanh tab trạng thái đơn (nhãn tham khảo, tên cuối cùng lấy theo trạng thái đơn của leescoffee_pos)
> - `ury-payment.png` — bố cục modal/trang thanh toán
> - `leescoffee-website.png` — nhận diện thương hiệu (màu đỏ, còn lại là cấu hình)

> **Lưu ý ảnh:** Một số ảnh URY hơi mơ hồ ở chi tiết nhỏ (ví dụ tên chính xác từng tab, tên phương thức thanh toán) → ghi là "cần xác nhận", không tự bịa.

## 1. Bố cục tổng quan (Layout Overview)

### Trang POS (`/pos`) — tham chiếu `ury-pos.png`

```
[ POS Page (/pos) ]
┌─────────────────────────────────────────────────────────────────────┐
│ [Logo + Tên quán + Địa chỉ]  [Tìm món + Ctrl K]  [Avatar + Menu]   │ Header (sticky, trắng, viền mảnh)
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  [Chip filter menu]                                                 │ Body (split)
│  ┌──────────────────────────────┬──────────────────────────────────┐ │
│  │ Lưới món (grid auto-fill)    │ [Giỏ hàng - Cart sticky]         │ │
│  │ [Thẻ món: ảnh vuông, tên,    │ - Loại đơn: Tại quán / Mang đi   │ │
│  │  chấm size/tùy chọn, xN]     │ - Tên khách                      │ │
│  │ Cả thẻ bấm, không nút phụ    │ - Phương thức thanh toán         │ │
│  │ Món 1 size: thêm thẳng giỏ   │ - Dòng món gọn (VÙNG CUỘN DUY    │ │
│  │ Món nhiều size: mở SizeModal │   NHẤT): tên+size/tóm tắt, giá/± │ │
│  │ Size rate=null: mờ, không chọn│ - Chân giỏ cố định: ghi chú,     │ │
│  │                              │   điểm (gập), tổng, cảnh báo,    │ │
│  │                              │   nút Tạo đơn (luôn hiện)        │ │
│  └──────────────────────────────┴──────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

- Header: trắng (`--pos-surface`), viền dưới mảnh (`--pos-border`), cao 64px. Trái: logo + tên + địa chỉ từ `usePos().config.brand`. Giữa: ô tìm món + phím tắt `Ctrl K` (đọc/ghi qua `store/search.ts`). Phải: điều hướng Bán món/Đơn hàng + menu tài khoản (Chuyển sang Desk `/desk`, Xóa bộ nhớ đệm, Đăng xuất).
- Body: lưới món chiếm cột trái, giỏ hàng cột phải (sticky). Loại đơn, tên khách, thanh toán chuyển lên đầu giỏ (`.pos-order-setup`).
- Lưới món (2026-11-19): tab nhóm `.pos-menu-tabs` (sticky `top: 64px`, cuộn ngang): "Tất cả" + Item Group theo thứ tự
  xuất hiện trong menu + "Khác" (món không có `item_group`) cuối; tab sinh từ món có thật (không tab rỗng); ≤ 1 nhóm → ẩn thanh tab.
  Tab nhớ trong `store/menuFilter.ts` (giữ khi chuyển trang). Ô tìm Ctrl K tìm trên toàn bộ món bất kể tab; bấm tab khi đang tìm → xóa từ khóa.
- Thẻ món (`MenuCard`): nút bấm toàn thẻ, cao đồng đều 170px (`grid-auto-rows`), lưới `repeat(auto-fill, minmax(140px, 1fr))` gap 12px,
  bo 12px; ảnh khung vuông 110px (`object-fit: cover`, `loading="lazy"`, `decoding="async"`) trên nền trung tính, không ảnh = chữ cái đầu;
  tên 14px semibold tối đa 2 dòng (`title` đủ tên); badge `xN`; chấm `.pos-menu-card__dot` khi có size hoặc tùy chọn. **Không hiển thị giá.**
  `content-visibility: auto` cho danh sách dài. Hover / nhấn / focus: viền `--pos-primary`.
- Bấm thẻ: nhiều size → `SizeModal` (bấm hàng size = thêm ngay, tùy chọn mặc định); 1 size có `option_groups` → `OptionModal` (chọn
  tùy chọn, giá ở chân, "Thêm vào giỏ"); 1 size không tùy chọn → thêm thẳng; 1 size `rate=null` → thẻ mờ.
- Bảng chọn món dùng chung `ItemModalFrame` (đầu ảnh + tên + ×, thân cuộn, chân cố định); giá luôn ở cột phải
  (`.pos-size-row__price` / `.pos-item-modal__price`, `tabular-nums`).
- Giỏ hàng (làm gọn 2026-11-19):
  - Cột phải `.pos-page__side` cao `calc(100dvh - 98px)` (header 64 + đệm), sticky; `.pos-order-setup` cố định, `.pos-cart` flex 1.
    Trong giỏ chỉ `.pos-cart__lines` cuộn (**một vùng cuộn duy nhất**); header giỏ (có "Xoá giỏ") và `.pos-cart__footer` không cuộn.
  - Dòng món thu gọn (`.pos-cart-line__row`, grid `main | price` / `main | qty`): tên+size, tóm tắt tùy chọn 1 dòng (ellipsis,
    `title` đầy đủ) + nhãn CTKM ngắn "−10%"; giá; stepper (vùng chạm 44px, mặt nút 32px). Bấm vùng tên mở chip (chỉ 1 dòng mở).
  - Khu chip: nhãn nhóm cùng hàng với chip (grid 64px | chips), chip mặt 30px trong nút 44px, "Xoá món" ở cuối khu chip.
  - Chân giỏ: hàng gập "Ghi chú đơn hàng" (bấm mới hiện textarea) và "Dùng điểm" (bấm mới hiện stepper); Tạm tính / Khuyến mãi /
    Phụ thu / Đổi điểm / Tổng cộng luôn hiện; cảnh báo + `pos-create-bar` do `POS.tsx` truyền qua `children`.
  - Breakpoint: ≥ 1024px giữ 2 cột (giỏ 340px, 320px khi ≤ 1180px); < 1024px xếp dọc, cột phải `height: auto`, cuộn theo trang.
- Price List lấy từ menu đầu tiên có `price_list`. Box lỗi chỉ hiện khi `!loading && !priceList`. Lỗi tạo đơn hiện cạnh nút Tạo đơn.
- **Không còn footer nav** (thanh điều hướng dưới) — điều hướng nằm ở Header.

### Trang Orders (`/pos/orders`) — tham chiếu `ury-orders.png` + `ury-orders-tabphache.png`

```
[ Orders Page (/pos/orders) ]
┌─────────────────────────────────────────────────────────────────────┐
│ [Logo + Tên quán]  [Tìm đơn]  [Tên user / Avatar]                  │ Header (sticky)
├──────────────────┬─────────────────────────────────────────────────┤
│ [Tab trạng thái] │ [Danh sách đơn theo tab]                        │ Body
│ (trái - sidebar) │                                                 │
│ - Chờ thanh toán     │ [Đơn 1] [Đơn 2] [Đơn 3]  (grid / list)          │
│ - Đã thanh toán   │                                                 │
│ - Pha chế           │ [Chi tiết đơn được chọn]                        │
│                     │                                                 │
│ Nhãn = thực tế    │                                                 │
│ leescoffee_pos     │                                                 │
└────────────────────┴─────────────────────────────────────────────────┘
```

- Trái: tab 3 tabs — **Chờ thanh toán** (Draft), **Đã thanh toán** (Paid), **Pha chế** (kitchen). Nhãn từ thực tế không tham khảo; kiểm `custom_kitchen_status` + `payment_status`.
- Dưới tab: danh sách đơn theo tab; thẻ đơn có `customer_name`, `amount` (formatMoney), `name`, `order_type` tag (Mang đi/Tại quán), buzzer, **"Chờ QR"** khi `payment_status="Đang chờ"`, bếp status, giờ tạo. Ô tìm header (`store/search`) lọc mã đơn/tên khách.
- Phải: panel chi tiết 380px, sticky: khách + mã + loại, dòng món (chuỗi tùy chọn `formatOptions`), tổng, ghi chú, bếp; nút 52px: Thu tiền / QR / Hủy (viền đỏ); Xác nhận lấy chỉ Dine In Paid + bếp "Đã hoàn thành". Hủy đơn: hộp xác nhận + "Đang chờ QR" hiển cảnh báo → tự force=1. Nhãn thống nhất; key món có index; bỏ nút Quay lại Bán.

### Thanh toán (Payment) — tham chiếu `ury-payment.png`

```
[ Modal / Trang thanh toán ]
┌─────────────────────────────────────────────────────────────────────┐
│ [Payment] ×                                                          │ Header modal
├──────────────────────────┬──────────────────────────────────────────┤
│ % Apply Discount         │ [Order Summary]                          │
│ [Enter %] [Apply]        │ Subtotal    VND 2500000                  │
│                          │ Total       VND 2500000                  │
│ Payment Methods          │                                          │
│ [QR Bank Transfer]       │   [Pay VND 2500000]                      │
│ [Cash]  ← được chọn      │                                          │
│                          │                                          │
│ Cash Received            │                                          │
│ [250000₫]                │                                          │
│                          │                                          │
│ Total     VND 2500000    │                                          │
│ Change   VND 0           │                                          │
└──────────────────────────┴──────────────────────────────────────────┘
```

- Bố cục theo `ury-payment.png`: trái là phiếu giảm giá + phương thức thanh toán + tiền khách trả/tổng/tiền thối; phải là order summary + nút thanh toán.
- **Phương thức thanh toán lấy từ dữ liệu thật qua API** (`payment_modes` từ `get_pos_config`). Không hardcode tên ngân hàng, không hardcode "MoP" cụ thể, không hardcode số tiền ví dụ.
- Nút thanh toán chính dùng `--pos-primary` (đỏ thương hiệu).

## 2. Kiến trúc component (Component Architecture)

### Cấu trúc thư mục
```
src/
├── main.tsx              # BrowserRouter basename="/pos", mount pages
├── App.tsx               # Layout: Header + Outlet
├── types.ts              # TypeScript interfaces (KitchenOrder, KitchenItem...)
├── lib/
│   ├── api.ts             # fetch helpers + wrapper pos_api (Kitchen api methods)
│   └── pos-context.tsx    # Context: config, menus, loading/error
├── store/
│   ├── cart.ts            # zustand store (cart lines in memory)
│   └── search.ts          # zustand: keyword để phân trang / lọc món
├── components/
│   ├── AppHeader.tsx      # Header + NavLink pha chế + ô tìm trang (đổi theo trang)
│   ├── MenuGrid.tsx       # Tab nhóm (Item Group) + lưới món (MenuCard → SizeModal / OptionModal)
│   ├── ItemModalFrame.tsx # Khung chung bảng chọn món (đầu, thân cuộn, chân giá)
│   ├── OptionModal.tsx    # Món 1 size có tùy chọn: chip + giá + Thêm vào giỏ
│   ├── OptionChips.tsx    # Chip tùy chọn dùng chung (giỏ + OptionModal)
│   ├── CartPanel.tsx      # Giỏ hàng: lines, chip tùy chọn (lib/options.ts), ghi chú, tổng
│   ├── CustomerPicker.tsx # Tìm khách + tạo mới (debounced search, dropdown)
│   ├── QrModal.tsx        # Hiển thị QR thanh toán
│   ├── SizeModal.tsx      # Chọn size: hàng "nhãn …… giá"
│   └── PaymentModal.tsx    # Stub - thanh toán (khởi tạo sau, theo ràng buộc dự án)
├── pages/
│   ├── POS.tsx            # Chọn món, tạo đơn (loại đơn, khách, MOP, priceList)
│   ├── Orders.tsx         # Quản lý đơn: Chờ thanh toán / Đã thanh toán (2 tab, không Pha chế)
│   ├── Kitchen.tsx        # Quầy pha chế (mẫu cho skill)
│   └── Table.tsx          # Stub
└── styles/
    └── global.css          # CSS variables + layout (hoàn thành .pos-kitchen*)
```

### Cấu hình routing
```tsx
// BrowserRouter basename="/pos"
// website_route_rules map /pos/<path:app_path> → "pos" → www/pos.html

Routes:
  /pos           → POS.tsx          (Trang chính)
  /pos/orders    → Orders.tsx        (Quản lý đơn — 2 tab: Chờ thanh toán / Đã thanh toán)
  /pos/kitchen   → Kitchen.tsx      (Quầy pha chế)
  /pos/table     → Table.tsx        (Stub - placeholder)

## 3. Phân rẽ component (Component Breakdown)

### POS.tsx (Trang đặt hàng chính)

**State:**
- `orderType: 'Take Away' | 'Dine In'`
- `customerName: string`
- `modeOfPayment: string` (từ `payment_modes` API)
- `priceList: string | null` — lấy từ menu đầu tiên có `price_list`
- `canSubmit: boolean` — `!submitting && !loading && lines.length > 0 && !!priceList`
- `cartStore` (zustand) — lines, totals, orderNote
- `search` (zustand) — từ khóa tìm món

**Luồng xử lý:**
1. Page load → fetch `get_pos_config` + `get_menu_items` (qua PosContext)
2. User chọn loại đơn (segmented: Tại quán / Mang đi)
3. User gõ tìm kiếm (toàn bộ món) hoặc chọn tab nhóm → lọc món
4. User bấm thẻ món → 1 size không tùy chọn: thêm thẳng giỏ; nhiều size: SizeModal; 1 size có tùy chọn: OptionModal
5. User chọn size → thêm vào cart
6. Ở giỏ: chọn chip tùy chọn (mặc định chọn sẵn; nhóm bắt buộc chưa chọn chặn Tạo đơn), nhập ghi chú đơn (footer × `orderNote` → lưu `order_note`) — đã triển khai trên backend.
7. User bấm "Tạo đơn" → `create_draft_order({price_list})` → chuyển `/pos/orders?draft=<name>` + xóa cart
   - Disabled khi thiếu priceList hoặc không có món

**Component chính:**
- `OrderTypeToggle` (Tại quán / Mang đi)
- `CustomerPicker` (debounced search + tạo mới — thay thế `CustomerInput` text field)
- `PaymentMethodSelect` (dropdown từ API)
- `CreateOrderButton` (primary action)
- `SizeModal` (mở khi bấm thẻ món)
- Ghi chú đơn: `orderNote` (zustand) → textarea footer → gửi `order_note` khi tạo đơn

### Orders.tsx (Quản lý đơn — mẫu cho skill; rút lại Pha chế tab)

**State:**
- `tab`: "draft" | "paid" — chỉ 2 tab: Chờ thanh toán / Đã thanh toán
- `drafts[]`, `paid[]` — mỗi tỷ lệ dữ liệu riêng
- `selected`: string|null — mã đơn được chọn
- `detail`, `qr`, `confirmCancel`, `busy`, `loading`, `error`

**Luồng xử lý:**
1. Load → `Promise.all([getOrders("draft"), getOrders("paid")])`
2. Poll mỗi 10s — refresh danh sách (không getStatusBoard / board)
3. Nếu `?draft=<name>` trong URL → tự chọn đó
4. Match search: mã đơn OR tên khách (lowercase includes)
5. Hành động trên đơn đã chọn:
   - Draft: `payCash()` / `generateQr()` / Hủy đơn (viền đỏ)
   - Dine In Paid + kitchen "Đã hoàn thành": `confirmPickup()` → reset buzzer

**Hộp xác nhận hủy (destructive rule):**
- Bấm Hủy đơn → modal pop-up "Hủy đơn X?" → giữ/hủy
- Đơn `payment_status="Đang chờ"` → hiển cảnh báo "Đang chờ QR · Hãy chắc chắn khách chưa chuyển tiền"
- Cần `force=1` trừ khi đã chuyển tiền
- Không để tự bay: luôn có xác nhận

### Kitchen.tsx (Quầy pha chế — đã triển khai, mẫu cho skill)

**State:**
- `orders[]`, `tab`: "Chưa làm" | "Đã làm" | "Đã hoàn thành", `busy`, `error`, `loading`
- `now` — số giây trễ tính theo mở khung thời gian (refresh every 30s)

**Luồng xử lý:**
1. Load → `api.getKitchenOrders()` → Order by creation asc (backend chịu)
2. Tự refresh 5s (khung chính), update now every 30s
3. Tab: chỉ 3 tab; "Đã hoàn thành" chỉ hiện đơn ngày (`creation` startsWith localToday)
4. Advance: click "Đã làm" / "Đã hoàn thành" → `setKitchenStatus(name, status)` → reload

**Mẫu thẻ đơn:**
- Chữ lớn, [#{seq}] mã / khách, loại, thẻ rung, thời gian chờ (>=5 phút vàng, >=10 phút đỏ)
- Dòng món: tên + mỗi nhóm tùy chọn một chip `pos-chip-opt` (`optionParts`), món không có tùy chọn thì không có chip
- Ghi chú nổi bật (`pos-kcard__note`)
- Nút hành động lớn 56px; busy = `disabled={busy === name}`

**Ẩn ô tìm header ở /kitchen (AppHeader thay đổi theo trang):** placeholder "Tìm món…" / "Tìm đơn…". Số lượng đơn hiển thị tổng `counts[tab]`.

### BuzzerPicker.tsx (Chọn thẻ rung — đã triển khai, mẫu cho skill)

**State:** `list[]` (BuzzerOption[]), `error`, tự refresh 5 giây khi mở, Esc đóng.

**Luồng xử lý:**
1. Khi mở popup → `api.getBuzzers()` → lưới thẻ, legend "Sẵn sàng" (xanh) / "Đang dùng" (xám)
2. Thẻ `available=true` → bấm được, `available=false` → disabled, title "Đang giữ cho đơn {used_by}"
3. Bấm thẻ → `onPick(b)` → đóng popup; chọn lại được (nút "Chọn thẻ rung" ở POS)
4. Khi chọn "Tại quán" → tự mở popup; chọn "Mang đi" → xóa thẻ đã chọn

**Mẫu thẻ:**
- Kích thước tối thiểu 84×84px (ô chọn bao gồm thumbnail + label)
- `.pos-buzzer` + `.pos-buzzer--ok` (xanh) / `.pos-buzzer--busy` (xám); `.pos-buzzer--selected` (xanh đặc)
- `.pos-dot` (10×10px) + `.pos-dot--ok` / `.pos-dot--busy`

### Table.tsx (Stub)
- Chỉ là placeholder — không triển khai (theo ràng buộc dự án).

## 4. API Mapping

| Component | Gọi API | Phản hồi |
|---|---|---|
| AppHeader.tsx | `getPosConfig()` (qua PosContext) | `{ brand, branch, profile, payment_modes }` |
| MenuGrid.tsx | `getMenuItems()` (qua PosContext) | `[{ name, price_list, items: [{ name, image, item_group, sizes: [{ label, item_code, rate }], option_groups }] }]` |
| POS.tsx | `createDraftOrder()` | `{ invoice_name, grand_total, qty_sum, buzzer_number }` |
| Orders.tsx | `getOrders("draft"|"paid")` | `[{ name, customer_name, amount, status, order_type, buzzer_number, custom_kitchen_status, payment_status, creation }]` |
| Orders.tsx (Kitchen tab rút) | `getOrders("paid")` | chỉ trả `[{ name, customer_name, amount, status, order_type, buzzer_number, custom_kitchen_status, payment_status, creation }]` — Pha chế bây giờ ở Kitchen.tsx riêng |
| POS.tsx | `createDraftOrder()` + `buzzer` | Dine In bắt buộc chọn thẻ (via `BuzzerPicker`) trước khi Tạo đơn; gửi `buzzer` vào create order; Take Away bỏ qua |
| Orders.tsx | `getOrderDetails(name)` | `{ name, customer_name, order_type, items:[{item_code,item_name,qty,amount,sugar_level,ice_level}], payments, order_note, custom_kitchen_status, buzzer_number }` |
| Orders.tsx | `payCash(name)` | `{ invoice_name, status, payment_status, amount, currency }` |
| Orders.tsx | `generateQr(name)` | `{ invoice_name, payment_code, qr_url, amount, payment_status, idempotent }` |
| Orders.tsx | `confirmPickup(name)` | `{ invoice_name, buzzer_number }` |
| Orders.tsx | `cancelDraftOrder(name, force=0)` | `{ invoice_name, buzzer_number, message }` |
| Kitchen.tsx | `getKitchenOrders()` | `[{ name, customer_name, order_type, items:[{item_code,item_name,qty,sugar_level,ice_level}], order_note, buzzer_number, kitchen_status, creation }]` — lọc theo tab (Chưa làm / Đã làm / Đã hoàn thành) |
| Kitchen.tsx | `setKitchenStatus(invoice_name, status)` | `{ invoice_name, kitchen_status }` |
| Kitchen.tsx | Toast: tự hiện khi chuyển Chưa làm → Đã làm trong vòng 5 giây, bấm vào toast để đóng sớm |
| BuzzerPicker.tsx | `getBuzzers()` | `[{ name, buzzer_number, status, branch, available, used_by }]` |

**Lưu ý API `MenuItem`:** dùng `item.name` (không phải `item.item_name`), `item.sizes[]` (không phải `item.item_code` ở cấp trên). `rate` nằm trong mỗi `sizes[]` item.

## 5. Kiến trúc CSS (CSS Architecture)

Tất cả style trong `global.css`:
- CSS biến (tokens) tại `:root`: `--pos-primary`, `--pos-bg`, `--pos-surface`, `--pos-surface-alt`, `--pos-text`, `--pos-text-muted`, `--pos-border`, `--pos-success`, `--pos-warning`, `--pos-error`, `--pos-radius`, `--pos-shadow`
- Tên class ngữ nghĩa — **Orders.tsx**: `.pos-orders-page`, `.pos-tabs`, `.pos-tab`, `.pos-tab__count`, `.pos-orders-layout`, `.pos-orders-list`, `.pos-order-grid`, `.pos-order-card`, `.pos-order-card--static`, `.pos-order-card__top`, `.pos-order-card__price`, `.pos-order-card__meta`, `.pos-order-card__time`, `.pos-tag--warn`, `.pos-order-detail`, `.pos-order-detail__head`, `.pos-order-detail__name`, `.pos-order-detail__sub`, `.pos-order-detail__items`, `.pos-order-detail__total`, `.pos-order-detail__kitchen`, `.pos-order-detail__note`, `.pos-detail__row`, `.pos-detail__opts`, `.pos-ok`, `.pos-pending`, `.pos-detail__item-main`, `.pos-confirm`, `.pos-modal-backdrop`, `.pos-btn--danger`, `.pos-btn--danger-solid`, `.pos-status__badge`, `.pos-empty`
- **Kitchen.tsx**: `.pos-kitchen`, `.pos-kitchen-grid`, `.pos-kcard`, `.pos-kcard--late`, `.pos-kcard--warn`, `.pos-kcard--ok`, `.pos-kcard__seq`, `.pos-kcard__id`, `.pos-kcard__tags`, `.pos-kcard__items`, `.pos-kcard__line`, `.pos-kcard__qty`, `.pos-kcard__name`, `.pos-kcard__opts`, `.pos-chip-opt`, `.pos-kcard__note`, `.pos-kcard__foot`, `.pos-kcard__wait`, `.pos-kcard__btn`
- Các mẫu tiện ích: `.pos-btn`, `.pos-tag`, `.pos-badge`, `.pos-status__badge`
- Không inline styles — tất cả qua class
- Không CSS framework bên ngoài (không MUI, không Tailwind)

## 6. Tiêu chuẩn thân responsiveness (Touch-Friendly Standards)

- **Nút hành động trên máy POS:** tối thiểu 44×44px (Stepper vùng nhấn lớn hơn; ÷/− là 44px)
- **Dropdown/mục chạm:** tối thiểu 44px cao
- **Destructive actions (hủy đơn):** nằm dưới hộp xác nhận 52px — không tự bay, không ấn gấp. Không dùng nút mặc định đơn giản.
- **Kitchen card:** nút "Đã làm" / "Đã hoàn thành": 56×56px; màu theo mức khẩn cấp (`late` >10 phút đỏ, `warn` ≥5-10 phút vàng, `ok` <5 phút bình thường); chỉ 1 nút hành động mỗi thẻ; chữ đọc từ xa
- Khoảng cách giữa các mục chạm: 8px tối thiểu
- Size of critical actions được khai triển: `.pos-order-detail__actions .pos-btn { min-height: 52px; font-size: 16px }`
- **BuzzerPicker:** modal lưới thẻ tối thiểu 84×84px; `.pos-dot` (10×10px) “Sẵn sàng” (xanh), “Đang dùng” (xám); `.pos-buzzer-chosen` có viền nổi bật; nút “Chọn thẻ rung” 44px; tự refresh 5s, Esc đóng

```css
/* >= 640px (tablet) */
@media (min-width: 640px) {
  .pos-page--split {
    grid-template-columns: minmax(0, 1fr) 340px;
  }
}

/* >= 1024px (desktop) */
@media (min-width: 1024px) {
  /* layout rộng hơn */
}
```
