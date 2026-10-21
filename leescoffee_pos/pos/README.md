# POS Frontend

Frontend của màn hình POS cho app `leescoffee_pos` — React + TypeScript, build bằng Vite.

## Stack

- **React 18** + **TypeScript**
- **Vite 5** (dev server + build)
- **react-router-dom 6** (điều hướng client-side)
- **zustand** (state giỏ hàng)
- CSS thuần + CSS variables (không dùng UI framework)

## Cấu trúc

```text
leescoffee_pos/pos/
├── README.md
├── package.json
├── vite.config.ts
├── tsconfig.json
├── pos.html                 # entry của Vite (không phải trang Frappe phục vụ)
└── src/
    ├── main.tsx             # mount React, BrowserRouter basename="/pos"
    ├── App.tsx              # khung app: header + outlet
    ├── types.ts             # kiểu dữ liệu dùng chung
    ├── lib/
    │   ├── api.ts           # fetch helper + wrapper cho pos_api
    │   └── pos-context.tsx  # context: config (brand, POS Profile, MoP) + menu
    ├── store/
    │   └── cart.ts          # zustand: giỏ hàng (chỉ trong RAM, không localStorage)
    ├── components/
    │   ├── AppHeader.tsx    # logo + tên thương hiệu (đọc từ API)
    │   ├── MenuGrid.tsx     # lưới món theo nhóm menu
    │   ├── CartPanel.tsx    # giỏ hàng + tổng tiền
    │   └── QrModal.tsx      # hiển thị mã VietQR
    ├── pages/
    │   ├── POS.tsx          # chọn món, chọn loại đơn, tạo đơn Draft
    │   ├── Orders.tsx       # danh sách đơn, thu tiền, trạng thái bếp
    │   └── Table.tsx        # (stub) quản lý bàn — hoãn, xem CLAUDE.md mục 3
    └── styles/global.css    # CSS variables + layout
```

## Build

Vite build ra `leescoffee_pos/public/pos/` (thư mục `public` của app Frappe).
Frappe phục vụ asset tại `/assets/leescoffee_pos/pos/` — trang `www/pos.html`
trong app tham chiếu `pos.js` + `pos.css` (tên file cố định, không hash).

```bash
cd leescoffee_pos/pos
npm install
npm run build
```

Kết quả:

```text
leescoffee_pos/public/pos/
├── pos.js
├── pos.css
└── pos.html
```

> `public/pos/` là **output build**, không phải source — không sửa tay file trong này.
> Nếu thư mục này bị `.gitignore`, cần copy sang bench thật bằng tay (xem CLAUDE.md mục 4).

## Chạy dev (gọi API về bench thật)

```bash
cd leescoffee_pos/pos
npm run dev     # http://localhost:5173, proxy /api -> http://localhost:8000
```

## Mount & route

- React mount vào `<div id="root"></div>` trong `leescoffee_pos/www/pos.html`.
- Trang `www/pos.html` tự chứa CSRF token (do `www/pos.py` inject) và `window.POS_CONFIG`.
- `website_route_rules` trong `hooks.py` map `/pos/<path:app_path>` → `pos`, nên các
  sub-route như `/pos/orders` vẫn render đúng trang.

| Route         | Page         |
| ------------- | ------------ |
| `/pos`        | `POS.tsx`    |
| `/pos/orders` | `Orders.tsx` |
| `/pos/table`  | `Table.tsx`  |

## API

Mọi hàm nằm ở `leescoffee_pos/leescoffee_pos/api/pos_api.py`, được expose tự động:

```text
POST /api/method/leescoffee_pos.leescoffee_pos.api.pos_api.<tên_hàm>
```

Danh sách hàm: `get_pos_config`, `get_menu_items`, `get_buzzers`,
`create_draft_order`, `get_orders`, `get_order_detail`, `pay_cash`, `generate_qr`,
`confirm_pickup`, `get_status_board`.

## Ghi chú

- **Không hardcode** branding Lee's Coffee: tên quán/logo/banner đọc từ
  `Branch` / `Leescoffee POS Settings` qua `get_pos_config` → `get_brand_info()`.
- Màu chủ đạo nằm ở biến CSS `--pos-accent` (mặc định nâu cà phê trung tính).
- Giỏ hàng chỉ tồn tại trong RAM của tab đang mở — đóng tab là mất giỏ.
