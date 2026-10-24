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
│  │  chip "N size", badge qty]   │ - Tên khách                      │ │
│  │ Cả thẻ bấm, không nút phụ    │ - Phương thức thanh toán         │ │
│  │ Món 1 size: thêm thẳng giỏ   │ - Dòng món: tên+size, giá,       │ │
│  │ Món nhiều size: mở SizeModal │   Đường/Đá 50/70/100%, +/− 44px  │ │
│  │ Size rate=null: mờ, không chọn│ - Ghi chú đơn (footer)           │ │
│  │                              │ - Nút Tạo đơn (disabled khi      │ │
│  │                              │   thiếu Price List)              │ │
│  └──────────────────────────────┴──────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

- Header: trắng (`--pos-surface`), viền dưới mảnh (`--pos-border`), cao 64px. Trái: logo + tên + địa chỉ từ `usePos().config.brand`. Giữa: ô tìm món + phím tắt `Ctrl K` (đọc/ghi qua `store/search.ts`). Phải: điều hướng Bán món/Đơn hàng + menu tài khoản (Chuyển sang Desk `/desk`, Xóa bộ nhớ đệm, Đăng xuất).
- Body: lưới món chiếm cột trái, giỏ hàng cột phải (sticky). Loại đơn, tên khách, thanh toán chuyển lên đầu giỏ (`.pos-order-setup`).
- Chip lọc menu (`.pos-chip`) + chip lọc từ khóa tìm (qua `useSearch`).
- Thẻ món (`MenuCard`): nút bấm toàn thẻ, ảnh vuông (`pos-menu-card__media`), tên luôn hiển thị 2 dòng, chip "N size", badge số lượng. Không hiển thị giá. Món 1 size (label rỗng) thêm thẳng giỏ; nhiều size mở `SizeModal`; size `rate=null` mờ, không chọn được.
- Giỏ hàng: mỗi dòng có tên+size, giá, nút xóa, Đường/Đá 50/70/100% (đã sửa đảo nhãn), nút +/− 44px; ghi chú đơn ở footer; trạng thái giỏ trống.
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
- Phải: panel chi tiết 380px, sticky: khách + mã + loại, dòng món (Đường x%·Đá y%), tổng, ghi chú, bếp; nút 52px: Thu tiền / QR / Hủy (viền đỏ); Xác nhận lấy chỉ Dine In Paid + bếp "Đã hoàn thành". Hủy đơn: hộp xác nhận + "Đang chờ QR" hiển cảnh báo → tự force=1. Nhãn thống nhất; key món có index; bỏ nút Quay lại Bán.

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
│   ├── MenuGrid.tsx       # Chip filter menu + lưới món (MenuCard + SizeModal)
│   ├── CartPanel.tsx      # Giỏ hàng: lines, Đường/Đá, ghi chú, tổng
│   ├── CustomerPicker.tsx # Tìm khách + tạo mới (debounced search, dropdown)
│   ├── QrModal.tsx        # Hiển thị QR thanh toán
│   ├── SizeModal.tsx      # Modal chọn size (ảnh, tên, lưới size)
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
3. User gõ tìm kiếm hoặc chọn chip menu → lọc món
4. User bấm thẻ món → nếu 1 size: thêm thẳng giỏ; nếu nhiều size: mở SizeModal
5. User chọn size → thêm vào cart
6. Ở giỏ: chỉnh Đường/Đá 50/70/100%, nhập ghi chú đơn (footer × `orderNote` → lưu `order_note`) — đã triển khai trên backend.
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
- Dòng món: tên + chip "Đường x%·Đá y%"
- Ghi chú nổi bật (`pos-kcard__note`)
- Nút hành động lớn 56px; busy = `disabled={busy === name}`

**Ẩn ô tìm header ở /kitchen (AppHeader thay đổi theo trang):** placeholder "Tìm món…" / "Tìm đơn…". Số lượng đơn hiển thị tổng `counts[tab]`.

### Table.tsx (Stub)
- Chỉ là placeholder — không triển khai (theo ràng buộc dự án).

## 4. API Mapping

| Component | Gọi API | Phản hồi |
|---|---|---|
| AppHeader.tsx | `getPosConfig()` (qua PosContext) | `{ brand, branch, profile, payment_modes }` |
| MenuGrid.tsx | `getMenuItems()` (qua PosContext) | `[{ name, price_list, items: [{ name, sizes: [{ label, item_code, rate }] }] }]` |
| POS.tsx | `createDraftOrder()` | `{ invoice_name, grand_total, qty_sum, buzzer_number }` |
| Orders.tsx | `getOrders("draft"|"paid")` | `[{ name, customer_name, amount, status, order_type, buzzer_number, custom_kitchen_status, payment_status, creation }]` |
| Orders.tsx | `getOrders("paid")` + `getStatusBoard()` | tương tự + `[{ invoice_name, customer_name, kitchen_status, buzzer_number }]` |
| Orders.tsx | `getOrderDetails(name)` | `{ name, customer_name, order_type, items:[{item_code,item_name,qty,amount,sugar_level,ice_level}], payments, order_note, custom_kitchen_status, buzzer_number }` |
| Orders.tsx | `payCash(name)` | `{ invoice_name, status, payment_status, amount, currency }` |
| Orders.tsx | `generateQr(name)` | `{ invoice_name, payment_code, qr_url, amount, payment_status, idempotent }` |
| Orders.tsx | `confirmPickup(name)` | `{ invoice_name, buzzer_number }` |
| Orders.tsx | `cancelDraftOrder(name, force=0)` | `{ invoice_name, buzzer_number, message }` |
| Kitchen.tsx | `getKitchenOrders()` | `[{ name, customer_name, order_type, items:[{item_code,item_name,qty,sugar_level,ice_level}], order_note, buzzer_number, kitchen_status, creation }]` |
| Kitchen.tsx | `setKitchenStatus(invoice_name, status)` | `{ invoice_name, kitchen_status }` |

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
- **Kitchen card:** nút "Đã làm" / "Đã hoàn thành": 56×56px; màu theo mức khẩn cấp (`late` #d9703f, `warn` #d8a421, `ok` #3a9); chữ đọc từ xa ≥16px; chỉ 1 nút hành động mỗi thẻ
- Khoảng cách giữa các mục chạm: 8px tối thiểu
- Size of critical actions được khai triển: `.pos-order-detail__actions .pos-btn { min-height: 52px; font-size: 16px }`

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
