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
- **Đường/Đá đã lưu server**: `POS Invoice Item.sugar_level/ice_level` (Custom Field). Ghi chú đơn: `POS Invoice.order_note` (Custom Field). Backend handler gửi `sugar/ice` + `order_note` từ frontend.
- **`lib/api.ts` và `lib/pos-context.tsx` không được thay đổi** — giữ nguyên cách gọi API, CSRF.
- **Quy tắc khách hàng**: Always read from API (`search_customers`, `create_customer`), không hardcode tên khách; frontend `CustomerPicker` thay ô input cũ; checkout gửi `customer_name: customer?.name`; khi bấm tạo đơn → gửi `customer_name` là mã Customer hoặc để trống (backend tự dùng Walk-in Customer).

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

#### MenuGrid.tsx (kèm MenuCard + SizeModal)
- Chip lọc menu (`.pos-chip`, `pos-chip--is-active`) + chip lọc từ khóa tìm.
- `MenuCard`: toàn bộ thẻ là `button`, ảnh vuông (`pos-menu-card__media`), tên luôn hiện 2 dòng, chip "N size", badge số lượng. Không hiển thị giá.
- Món 1 size (label rỗng): thêm thẳng giỏ, không mở modal.
- Món nhiều size: mở `SizeModal`.
- Size `rate=null`: thẻ mờ (`pos-size-card--disabled`), không chọn được.
- `SizeModal`: `role="dialog"`, `aria-modal`, ảnh + tên ở đầu, lưới thẻ size lớn, tiền tệ từ `config.profile.currency`, Esc đóng.

#### CartPanel.tsx (CartPanel)
- Mỗi dòng: tên + size, giá, nút xóa, Đường/Đá 50/70/100%, nút +/− 44px.
- Sửa lỗi đảo nhãn Đường/Đá: `changeIceSugar(key, ice, sugar)` đúng thứ tự.
- Ghi chú đơn ở footer (`pos-cart__note-label`, `pos-input pos-textarea`).
- Trạng thái giỏ trống (`.pos-cart__empty`).
- Đường/Đá 50/70/100% (gửi `sugar`/`ice`); ghi chú đơn: footer textarea (`orderNote`) → gửi `order_note`. Backend thực hiện.
- Tương tác giỏ luôn qua `cartLineKey` (`${item_code}|${ice}|${sugar}`) cho `increment/decrement/remove` — cùng món khác đường/đá = dòng khác nhau. Thay đổi ice/sugar = đổi key dòng (merge hoặc replace).
- Ghi chú món per-line: `setNote(key, note)` cho từng dòng (`pos-cart-line__note`). Ghi chú đơn: `setOrderNote(note)` (textarea footer) — backend lưu `order_note`.

#### POS.tsx (Order Setup)
- `pos-order-setup`: loại đơn (Tại quán / Mang đi), `CustomerPicker` (tìm khách + tạo mới), thanh toán — chuyển lên đầu giỏ.
- `priceList`: lấy từ menu đầu tiên có `price_list`.
- Box lỗi: chỉ hiện khi `!loading && !priceList` (Thiếu Price List của menu).
- Lỗi tạo đơn: hiện cạnh nút Tạo đơn (qua `formError`).
- Nút Tạo đơn: `disabled={!canSubmit}`.
- Tạo đơn gửi `customer_name: customer?.name` (mã Customer); để trống → backend dùng Walk-in Customer.

#### Orders.tsx (Management — mẫu cho skill; rút lại Pha chế tab)
- Layout: tab 2 — Chờ thanh toán / Đã thanh toán → danh sách đơn lưới → panel chi tiết fixed 380px, sticky. Không Pha chế tab.
- Thẻ đơn: `customer_name`, `amount` (formatMoney), `name`, `order_type` tag, buzzer, **"Chờ QR"** `payment_status="Đang chờ"`, bếp status (khi phản hồi), giờ tạo.
- Ô tìm header lọc mã đơn/tên khách; key món có index.
- Panel chi tiết: khách + mã + loại, dòng món (Đường x%·Đá y%), tổng, ghi chú, bếp; nút 52px: Thu tiền / QR / Hủy (viền đỏ).
- **Hủy đơn luôn có hộp xác nhận**; `payment_status="Đang chờ"` → cảnh báo + tự `force=1`.
- Tự refresh mỗi 10s; URL `?draft=<name>` → tự chọn đơn đó.
- Nhãn thống nhất "Tại quán"/"Mang đi"; bỏ nút "Quay lại bán hàng".

#### Kitchen.tsx (Quầy pha chế — mẫu cho skill, đã triển khai)
- Layout: tab 3 — Chưa làm / Đã làm / Đã hoàn thành → danh sách đơn lưới → số lượng hiển thị trong tab.
- Thẻ đơn: [#{seq}] mã, khách, loại, thẻ rung, thời gian chờ (>=5 phút vàng / >=10 phút đỏ).
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
7. **Màn pha chế:** đơn `custom_kitchen_status` rỗng không hiện trên Kitchen (backend `get_kitchen_orders` chỉ trả kèm status đã có); chữ lớn đọc từ xa; 1 nút hành động 56px mỗi thẻ; màu theo mức khẩn cấp (`late` ≥10 phút, `warn` ≥5 phút) — không dùng thêm màu thừa.

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
  changeIceSugar: (code, ice, sugar) => set((s) => ({
    lines: s.lines.map(l => l.code === code ? { ...l, ice, sugar } : l)
  })),
  setOrderNote: (note) => set({ orderNote: note }),
  clear: () => set({ lines: [], orderNote: '' }),
  total: () => get().lines.reduce((sum, l) => sum + l.price * l.qty, 0),
}));
```

> `CartLine` cần có thêm trường `ice` (50/70/100), `sugar` (50/70/100), `size` (được chọn trong SizeModal), `orderNote` (ghi chú đơn hàng).

### 3.4 Zustand store hiện tại (thực tế)

```typescript
// store/cart.ts — zustand, chỉ memory (không localStorage)
const ICE_SUGAR = [50, 70, 100] as const;

// Dòng giỏ phân biệt theo item_code + ice + sugar
export function cartLineKey(line: CartLine): string {
  return `${line.item_code}|${line.ice ?? 100}|${line.sugar ?? 100}`;
}

interface CartState {
  lines: CartLine[];
  add: (item: CartLine) => void;
  addVariant: (line: Omit<CartLine, "qty"> & { qty?: number }) => void;
  increment: (item_code: string) => void;
  decrement: (item_code: string) => void;
  remove: (item_code: string) => void;
  removeLine: (key: string) => void;
  changeIceSugar: (key: string, ice: number, sugar: number) => void;
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
- [ ] Mỗi dòng giỏ có chọn Đường/Đá 50/70/100, mặc định 100
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
