# Trạng thái & Quản lý State — Leescoffee POS

> Nguồn: `.claude/skills/pos-ui/layout.md` (bố cục, component, API mapping, checklist) +
> `.claude/docs/reference/` ( ảnh tham khảo URY + website).

## 1. Nguyên tắc thiết kế chính (Key Design Principles)

### 3.0 Quy tắc code (luôn tuân thủ khi viết component POS)

- **Dùng đúng tên field API**: `item.name`, `item.sizes`, `size.rate`; không dùng `item.item_name`/`item.item_code` ở cấp item. Kiểm tra `types.ts` khớp backend trước khi code.
- **Cả thẻ bấm được, không nút phụ**: `.pos-menu-card` là một `button` toàn bộ; không thêm nút "+ Thêm" riêng.
- **Đỏ chỉ cho điểm nhấn**: nút chính (Tạo đơn, chọn size), trạng thái active. Không tô cả vùng lớn (không `.pos-header` đỏ đặc).
- **Nền trắng, viền mảnh**: `--pos-bg: #FFFFFF`, `--pos-border: #E3E1E0`.
- **Vùng chạm tối thiểu 44px**: nút, input, stepper, dropdown, chip.
- **Luôn có trạng thái rỗng/tải/lỗi**: `.pos-empty` (chưa có menu, giỏ trống), loading (Đang tải menu…), `.pos-alert--error` (lỗi API, thiếu Price List).
- **Không nhúng thư viện UI**: CSS thuần + biến `--pos-*`.
- **Không hardcode thương hiệu**: tên/logo/banner lấy từ `usePos().config.brand`.
- **Tùy chọn món động (MYPOS Option)**: nhóm/giá trị lấy từ `option_groups` của món (`get_menu_items`), không hardcode tên nhóm. Gửi `options: [{group, value}]` mỗi dòng; server lưu `POS Invoice Item.options` (JSON). Hiển thị đơn dùng `options` server trả (đơn cũ dựng từ `sugar_level`/`ice_level`). Ghi chú đơn: `POS Invoice.order_note`.
- **`lib/api.ts` và `lib/pos-context.tsx`**: chỉ được đổi kiểu/khóa dữ liệu — giữ nguyên cách gọi API, CSRF.
- **Quy tắc khách hàng**: Always read from API (`search_customers`, `create_customer`), không hardcode tên khách; frontend `CustomerPicker` thay ô input cũ; checkout gửi `customer_name: customer?.name`; khi bấm tạo đơn → gửi `customer_name` là mã Customer hoặc để trống (backend dùng khách vãng lai của POS Profile — `custom_walk_in_customer`; chưa cấu hình → lỗi). Hiển thị tên khách qua `customerLabel(o)` (`lib/format.ts`, cờ `is_walk_in` do server trả → "Khách lẻ"), không so sánh tên Customer.

- **Màu loại đơn ≠ màu trạng thái**: Mang đi / Tại quán luôn hiển thị qua `OrderTypeChip`
  (`typeLabel`, `typeModifier` dùng chung, không viết lại); màu lấy từ `--pos-takeaway-*` / `--pos-dinein-*`
  (tokens.md §1.5c). Không dùng đỏ/vàng/`--pos-success` cho loại đơn. Thẻ Pha chế: viền trên = thời gian chờ,
  viền trái = loại đơn.

### 3.1 Xử lý thương hiệu whitelabel (KHÔNG hardcode!)

```tsx
// ✅ Đúng: đọc từ API
const { brand } = usePos();
<h1>{brand.name}</h1>
<img src={brand.logo} alt={brand.name} />

// ❌ Sai: hardcode
<h1>Lee's Coffee</h1>
<img src="/assets/leescoffee_pos/logo.png" />
```

**API endpoint:** `GET /api/method/leescoffee_pos.leescoffee_pos.api.pos_api.get_pos_config`
Trả về: `{ brand: { name, logo, banner, phone, address }, ... }`

### 3.2 Responsive thân chạm (Responsive Touch-Friendly)

**Kích thước mục chạm tối thiểu:** `44px x 44px` (iOS/Android UX guideline)
- Nút: `min-height: 44px; min-width: 44px;`
- Input: `min-height: 44px;`

**Breakpoint mobile-first:**
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

### 3.3 Mẫu component (Component Patterns) — thực tế hiện tại

#### AppHeader.tsx
- Header trắng (`--pos-surface`), viền dưới mảnh (`--pos-border`), cao 64px.
- Trái: logo + tên + địa chỉ từ `usePos().config.brand`.
- Giữa: ô tìm món (`pos-header__search-input`) + phím tắt `Ctrl K`; đọc/ghi qua `store/search.ts`.
- Phải: điều hướng Bán món/Đơn hàng (`pos-navlink`) + menu tài khoản (`pos-user`) — Chuyển sang Desk `/desk`, Xóa bộ nhớ đệm, Đăng xuất.

#### MenuGrid.tsx (kèm MenuCard, SizeModal)
- Tab nhóm `.pos-menu-tab` (`role="tab"`, `aria-selected`, `.is-active`), khóa tab = `item_group`, `NO_GROUP` = "Khác",
  `ALL_GROUPS` = "Tất cả" (`store/menuFilter.ts`). Tab đã nhớ không còn trong menu → hiển thị "Tất cả". Không có tên nhóm cứng.
- Có từ khóa tìm → lọc toàn bộ món, tab hiện "Tất cả"; bấm tab → `setSearch("")` rồi đổi tab.
- `MenuCard`: toàn bộ thẻ là `button` (`title` = tên), ảnh/chữ cái đầu, tên 2 dòng, badge `xN`. Không hiển thị giá, không có chấm báo size/tùy chọn.
- 1 size (có hoặc không `option_groups`): thêm thẳng giỏ với `defaultOptions`. Nhiều size: `SizeModal`. 1 size `rate=null`: thẻ mờ.
  (OptionModal đã bỏ 2026-11-19 — xem layout.md.)
- `ItemModalFrame`: `role="dialog"`, `aria-modal`, Esc / nền để đóng, khóa cuộn trang, focus nút ×; `onClose` giữ trong ref (effect chạy 1 lần).
  Chỉ render khi mở.
- `SizeModal`: hàng `.pos-size-row` (nhãn trái, giá phải), size `rate=null` → `.is-disabled` "Chưa có giá". Bấm hàng = thêm ngay.
- `OptionChips`: khu chip trong giỏ (nhãn nhóm cùng hàng, mặt chip 30px trong vùng chạm 44px, "+giá", "chưa chọn").

#### CartPanel.tsx (CartPanel)
- **CTKM hiện sẵn** (không dựa vào tooltip): `PromoChip` trong `.pos-cart-line__promos` dưới tóm tắt — "Giảm {discount_percentage}% · {title luật đầu}"
  (không có % → "Khuyến mãi"), nhiều luật → "+N" (`.pos-promo-chip__more`), `title` = nhãn đầy đủ. Dòng tặng (`is_free_item`) → "Tặng · {title}".
  Không CTKM → không render (không tăng chiều cao). Dữ liệu nguyên từ `preview_pricing` (`rules[].title`, `discount_percentage`), không tính lại.
  Chân giỏ: `.pos-cart__promo-names` dưới "Khuyến mãi" = `rules[].title` không trùng của mọi dòng preview, 1 dòng ellipsis.
- Mỗi dòng (thu gọn): tên + size, tóm tắt tùy chọn 1 dòng, chip CTKM (nếu có), giá, stepper −/+ (vùng chạm 44px). Nút "Xoá món" nằm trong khu chip khi mở; thu gọn thì `−` ở qty 1 xóa dòng (store).
- **Số lượng gõ trực tiếp** (`QtyInput` trong `CartPanel.tsx`, `.pos-qty__input` 44×44px, `inputMode="numeric"`): focus chọn hết; khi
  gõ chỉ giữ bản nháp cục bộ (không ghi store → không gọi `preview_pricing`); Enter / rời ô áp dụng qua `setQty` (store, kẹp
  1..`MAX_LINE_QTY` = 999); vượt 999 → cắt 999 + báo "Tối đa 999"; rỗng/0 → về số cũ; chữ/số âm → về số cũ + báo nhẹ; Esc → hủy.
  Không xóa dòng — xóa bằng `−` ở qty 1 hoặc "Xoá món". Khóa dòng không đổi → CTKM theo tổng qty mỗi mã qua preview như cũ.
- **Chip tùy chọn** (`lib/options.ts`): "Chọn 1" = chip radio (`role=radio`; nhóm không bắt buộc bấm lại để bỏ chọn, nhóm bắt buộc không bỏ được), "Chọn nhiều" = chip bật/tắt (`role=checkbox`). `.pos-optchip` là nút trong suốt cao 44px (vùng chạm), mặt chip `.pos-optchip__face` cao 30px, active = `--pos-primary`. Nhãn nhóm cùng hàng với chip (`.pos-optgroup` grid). Nhóm bắt buộc có dấu `*`; chưa chọn → nhãn màu `--pos-warning` + "chưa chọn".
- **Phụ thu topping**: chip có `extra_price > 0` hiện "+giá" (`.pos-optchip__price`); giá dòng giỏ gồm phụ thu; footer "Phụ thu topping +X" lấy `preview.total_surcharge` (server). Màn pha chế / tem ly chỉ tên, không giá (`options.md` §9b).
- **Thu gọn/mở**: mỗi lúc chỉ mở chip của 1 dòng (`expanded`); thêm món mới → mở nếu món có nhóm, không có nhóm thì thu dòng đang mở; `pointerdown` ra ngoài dòng đang mở (ref `openRef`) → thu. Dòng thu gọn: `.pos-cart-line__main` là `<button aria-expanded>` chứa tên + `.pos-cart-line__summary` ("Đường 70% · Đá 50% · Topping Trân châu (+10.000)").
- **Trạng thái thiếu bắt buộc**: dòng `.is-missing` (viền trái `--pos-warning`) + tóm tắt đổi thành "Chọn {nhóm}" (`.is-warn`); `POS.tsx` chặn Tạo đơn + nhắc nhẹ (trong chân giỏ).
- Chân giỏ (`.pos-cart__footer`, không cuộn): ghi chú đơn = hàng gập `.pos-cart__toggle` (bấm → `pos-input pos-textarea`, blur → thu), đổi điểm = `.pos-redeem` gập (`.pos-redeem__body` chứa stepper), tổng (`.pos-cart__sums`), gợi ý preview, rồi `children` (cảnh báo + `pos-create-bar` từ `POS.tsx`).
- Trạng thái giỏ trống (`.pos-cart__empty`).
- Gửi `options` mỗi dòng ở cả `preview_pricing` (khóa debounce gồm options) và `create_draft_order`; ghi chú đơn: footer textarea (`orderNote`) → gửi `order_note`.
- Tương tác giỏ luôn qua `cartLineKey` (`${item_code}|${group=value;...}`, options chuẩn hóa theo thứ tự cấu hình) cho `increment/decrement/remove` — cùng món khác tổ hợp tùy chọn = dòng khác nhau. `setLineOptions(key, options)` đổi key dòng (trùng dòng khác thì gộp qty) và trả key mới.
- Ghi chú món per-line: `setNote(key, note)` cho từng dòng (`pos-cart-line__note`). Ghi chú đơn: `setOrderNote(note)` (textarea footer) — backend lưu `order_note`.

#### POS.tsx (Order Setup)
- `pos-order-setup`: loại đơn (Tại quán / Mang đi), `CustomerPicker` (tìm khách + tạo mới), thanh toán — chuyển lên đầu giỏ.
- `priceList`: lấy từ menu đầu tiên có `price_list`.
- Box lỗi: chỉ hiện khi `!loading && !priceList` (Thiếu Price List của menu).
- Lỗi tạo đơn: hiện cạnh nút Tạo đơn (qua `formError`).
- Nút Tạo đơn: `disabled={!canSubmit}`.
- Tạo đơn gửi `customer_name: customer?.name` (mã Customer); để trống → backend dùng khách vãng lai của POS Profile (`config.profile.walk_in_configured = false` → banner cảnh báo + chặn tạo đơn không chọn khách).

#### Orders.tsx (Management — mẫu cho skill; rút lại Pha chế tab)
- Layout: tab 2 — Chờ thanh toán / Đã thanh toán → danh sách đơn lưới → panel chi tiết fixed 380px, sticky. Không Pha chế tab.
- Thẻ đơn: `customer_name`, `amount` (formatMoney), mã ngắn "#00016" (`title` = mã đầy đủ), `order_type` tag, buzzer, **"Chờ QR"**
  `payment_status="Đang chờ"`, "Đã đóng ca" (status Consolidated), bếp status, ngày giờ `formatOrderTime` ("Hôm nay 11:38").
- Thanh trên: MANAGER có segmented "Ca hiện tại | Lịch sử" (44px). Ca hiện tại = 2 tab + bộ đếm COUNT (đang tìm → đếm danh sách đã lọc),
  dòng "Ca mở lúc …", cảnh báo vàng `.pos-alert--warn` khi còn Draft ca trước. Lịch sử = Hôm qua · 7 ngày · Chọn ngày (`input type=date`)
  + "N đơn", nút "Xem thêm (x/N)"; trạng thái rỗng riêng cho từng chế độ.
- Ô tìm header lọc mã đơn (đầy đủ hoặc ngắn)/tên khách; key món có index.
- Panel chi tiết: khách + mã + loại, dòng món (Đường x%·Đá y%), tổng, ghi chú, bếp; nút 52px: Thu tiền / QR / Hủy (viền đỏ).
- **Hủy đơn luôn có hộp xác nhận**; `payment_status="Đang chờ"` → cảnh báo + tự `force=1`. Bắt buộc chọn lý do (`.pos-reason`, radio 44px:
  Khách đổi ý / Đặt nhầm / Khách không lấy / Khác + ghi chú bắt buộc); nút xác nhận khóa tới khi hợp lệ; gửi `reason`, `note`.
- Draft kênh khác QR: chi tiết "Tự hủy lúc HH:MM nếu chưa thanh toán" (`.pos-order-detail__auto`, theo `config.pos_draft_auto_cancel_minutes`,
  `lib/format.ts::autoCancelInfo`); thẻ có nhãn vàng "Tự hủy sau N phút" khi còn ≤ 30 phút.
- Tự refresh mỗi 10s; URL `?draft=<name>` → tự chọn đơn đó.
- Nhãn thống nhất "Tại quán"/"Mang đi"; bỏ nút "Quay lại bán hàng".

#### Kitchen.tsx (Quầy pha chế — mẫu cho skill, đã triển khai)
- Layout: tab 3 — Chưa làm / Đã làm / Đã hoàn thành → danh sách đơn lưới → số lượng hiển thị trong tab.
- Thẻ đơn: [#{seq}] mã, khách, loại, thẻ bàn ("Bàn #"), thời gian chờ (>=5 phút vàng / >=10 phút đỏ).
  - Tên khách (2026-11-24): `.pos-kcard__customer` dưới mã đơn, cả 3 tab, 14px/600 (nhỏ hơn tên món 20px/700), một dòng "…".
    `customerLabel(o)`: cờ `is_walk_in` của `get_kitchen_orders` → "Khách lẻ"; đơn QR hiện tên khách thật. Không so tên Customer.
- Toast sau "Đã làm" (5 giây, bấm để tắt sớm, không nút; một toast — `refreshServeQueue([tên đơn])` chặn toast thu ngân trùng):
  Mang đi "Đã báo quầy gọi khách {tên | khách lẻ} (#00080)"; Tại quán có thẻ "Đã báo quầy phục vụ bàn {số} (#00080)" (mã ngắn `shortOrderNo`);
  QR giữ "Đã báo khách {tên} (đặt QR) tới quầy nhận món" (khách tự nhận thông báo). Tại quán thiếu thẻ (dữ liệu cũ) → câu Mang đi.
- In (2026-11-24): phiếu pha chế ("In phiếu", `ReceiptModal kind="kitchen"`) có dòng "Khách: {customerLabel}" (đơn QR không thêm — đã có
  "Kênh: QR · tên"); tem ly (`CupLabels`) dòng cuối "Bàn #07 · {customerLabel}" / "{customerLabel}", một dòng "…". Hóa đơn khách không đổi.
- Dòng món: tên lớn + chip "Đường x%·Đá y%", ghi chú nổi bật.
- Nút hành động 56px: "Đã làm" (đỏ) / "Đã hoàn thành" (xanh); busy = `disabled={busy === name}`.
- Tự refresh 5 giây; update `now` every 30s; tab "Đã hoàn thành" lọc đơn ngày (`creation`).
- Ẩn ô tìm ở AppHeader: placeholder "Tìm đơn…" trên /orders, ẩn trên /kitchen.

#### Hộp xác nhận destructive rule (lặp lại cho Orders/POS)
- **Không hành động phá hủy** mà thiếu hộp xác nhận pop-up → viết code lại: gọi `<div className="pos-confirm">` rồi "giữ"/"hủy".
- Nút đang active (`disabled={busy}`) — bị vô hiệu hoá khi action chờ.
- Cảnh báo đối kháng: nếu `payment_status="Đang chờ"` → rõ ràng nhấn vào nút Hủy đồng nghĩa transfer đã xảy ra → làm bằng `force=1` + cảnh báo.

## 2. Quyết định nghiệp vụ POS (luật, không phải gợi ý)

Các quy tắc dưới đây là **luật nghiệp vụ**, phải được tuân thủ khi code component POS:

1. **Thẻ món KHÔNG hiển thị giá.** Bấm thẻ mở modal chọn size; giá chỉ hiện sau khi chọn size và trong giỏ. Chưa chọn size thì không thêm được vào giỏ.
2. **Mỗi dòng giỏ có chọn Đường và Đá:** 50 / 70 / 100 (%), mặc định 100%.
3. **Có ô "Ghi chú đơn hàng":** `POS Invoice.order_note` là Custom Field (Small Text) — đã tạo fixtures, backend sẽ lưu. UI frontend đã có textarea footer; `POS.tsx` gửi `orderNote.trim() || undefined` cho `createDraftOrder`.
4. **Màn hình cảm ứng:** vùng chạm tối thiểu 44px (áp dụng toàn bộ nút, input, stepper, dropdown).
5. **Destructive actions (hủy đơn) luôn kèm hộp xác nhận** — không tự bay, không ấn gấp. Không để chỉ nút Hủy đơn luôn trạng thái click.
6. **Không để nút Hủy đơn VẪN hiện khi đơn `payment_status="Đang chờ"`** — hay làm trigger xóa xong mà khách đã chuyển tiền: nút chảy red → thấy "Đang chờ QR" → nhấn đồng nghĩa transfer occurred → chọn `force=1` + cảnh báo.
7. **Màn pha chế:** đơn `custom_kitchen_status` rỗng không hiện trên Kitchen (backend `get_kitchen_orders` chỉ trả kèm status đã có); chữ lớn đọc từ xa; 1 nút hành động 56px mỗi thẻ; màu theo mức khẩn cấp (`late` ≥10 phút màu đỏ, `warn` ≥5 phút màu vàng, `ok` <5 phút bình thường) — không dùng thêm màu thừa.

## 3. Quản lý trạng thái (zustand)

```typescript
// Cart store - chỉ trong memory (không localStorage)
export const useCartStore = create<CartState>((set, get) => ({
  lines: [] as CartLine[],
  add: (item) => set((s) => ({ lines: [...s.lines, item] })),
  remove: (code) => set((s) => ({ lines: s.lines.filter(l => l.code !== code) })),
  changeQty: (code, qty) => set((s) => ({
    lines: s.lines.map(l => l.code === code ? { ...l, qty } : l)
  })),
  setLineOptions: (key, options) => /* đổi key dòng, gộp nếu trùng — xem 3.4 */ key,
  setOrderNote: (note) => set({ orderNote: note }),
  clear: () => set({ lines: [], orderNote: '' }),
  total: () => get().lines.reduce((sum, l) => sum + l.price * l.qty, 0),
}));
```

> `CartLine` có `options` (`[{group, value}]` đã chuẩn hóa) + `option_groups` (nhóm áp dụng cho món, từ `get_menu_items`), `size` (chọn trong SizeModal); ghi chú đơn ở `orderNote` của store.

### 3.4 Zustand store hiện tại (thực tế)

```typescript
// store/cart.ts — zustand, chỉ memory (không localStorage)
// Dòng giỏ phân biệt theo item_code + tổ hợp tùy chọn đã chuẩn hóa (lib/options.ts)
export function cartLineKey(line: Pick<CartLine, "item_code" | "options">): string {
  return `${line.item_code}|${optionsKey(line.options || [])}`;
}

interface CartState {
  lines: CartLine[];
  add: (item: CartLine) => void;
  addVariant: (line: Omit<CartLine, "qty"> & { qty?: number }) => void;
  increment: (item_code: string) => void;
  decrement: (item_code: string) => void;
  remove: (item_code: string) => void;
  removeLine: (key: string) => void;
  setLineOptions: (key: string, options: CartOption[]) => string; // trả key mới
  setNote: (key: string, note: string) => void;
  setOrderNote: (note: string) => void;
  clear: () => void;
  orderNote: string;
}

// store/search.ts — zustand
interface SearchState {
  search: string;
  setSearch: (s: string) => void;
}
```

> > **Lưu ý quan trọng:** `increment`/`decrement/remove` hiện tại theo `cartLineKey` — cùng món khác đường/đá là dòng khác nhau. Không theo `item_code`.

## 4. Tích hợp API (API Integration Pattern)

```typescript
// lib/api.ts — không được thay đổi, giữ nguyên cách gọi
const API_BASE = "/api/method/leescoffee_pos.leescoffee_pos.api.pos_api";

function csrfToken(): string {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta?.getAttribute("content") || window.POS_CONFIG?.csrfToken || "";
}

export async function call<T>(method: string, args: Record<string, unknown> = {}): Promise<T> {
  const response = await fetch(`${API_BASE}.${method}`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-Frappe-CSRF-Token": csrfToken(),
    },
    body: JSON.stringify(args),
  });
  // Frappe v16: {"message": {...}}
  const data = await response.json();
  if (!response.ok) throw new Error(extractError(data, response.status));
  const payload = data?.message ?? data;
  return payload as T;
}

export const api = {
  getPosConfig: () => call<PosConfig>("get_pos_config"),
  getMenuItems: () => call<unknown[]>("get_menu_items"),
  createDraftOrder: (p: {
    items: Array<{ item_code: string; qty: number }>;
    order_type: string;
    customer_name?: string;
    mode_of_payment?: string;
    branch_name?: string;
    price_list?: string;
  }) => call<CreatedOrder>("create_draft_order", p),
  // ... getOrders, getOrderDetail, payCash, generateQr, confirmPickup, getStatusBoard
};
```
```

## 5. Quy ước đặt tên file (File Naming Convention)

- Component: `PascalCase.tsx` → `MenuGrid.tsx`, `CartPanel.tsx`
- Hook: `useXxx.ts` → `usePos.ts`, `useMenu.ts`
- Style: `component.css` → tích hợp trong `global.css` hoặc module riêng

## 6. Checklist trước khi commit component

- [ ] Không hardcode bất kỳ thông tin thương hiệu nào (tên, logo, màu, banner)
- [ ] CSS dùng biến `--pos-*` từ `global.css`, không định nghĩa màu mới
- [ ] Component responsive (xem lại media queries cần thiết)
- [ ] Touch target đủ >= 44px
- [ ] Destructive actions (hủy đơn) **có hộp xác nhận**, không tự bay
- [ ] TypeScript types khớp với API response (`types.ts`)
- [ ] Thẻ món không hiển thị giá (giá chỉ sau chọn size + trong giỏ)
- [ ] Tùy chọn món lấy từ `option_groups` (không hardcode nhóm/giá trị); mặc định chọn sẵn; nhóm bắt buộc chưa chọn chặn Tạo đơn; món không có nhóm không hiện chip
- [ ] Có ô ghi chú đơn hàng (footer × `orderNote` → lưu `order_note`; đã triển khai backend)
- [ ] Phương thức thanh toán lấy từ API, không hardcode tên ngân hàng/MoP

## 7. Tham khảo thiết kế

- **URY POS Layout:** Thanh header cố định, menu dạng grid 2-3 cột, cart panel bên phải hoặc dưới cùng tùy width
- **ERPNext POS:** Giao diện đơn giản, tập trung vào workflow tạo đơn → thanh toán → xong

## 8. White-Label Compliance Checklist

- [ ] Không hardcode "Lee's Coffee" hoặc tương tự trong JSX/văn bản
- [ ] Không hardcode logo/hình ảnh thương hiệu
- [ ] Màu từ CSS biến, không litteral
- [ ] Tất cả văn bản động từ phản hồi API
- [ ] Màu thương hiệu áp dụng qua biến `--pos-primary` (một chỗ duy nhất trong `references/tokens.md`)
- [ ] Trạng thái thẻ bàn lấy từ API `available` (Sẵn sàng / Đang dùng), không suy suy đoán tự build
- [ ] Toast thông báo ở màn Pha chế tự động đóng sau 5 giây, click để tắt sớm
