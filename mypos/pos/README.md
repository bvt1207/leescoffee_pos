# MYPOS Frontend

Frontend React + TypeScript của app `mypos`, build bằng Vite. Có 2 bundle độc lập:

| Bundle | Config | Nguồn | Output | Trang Frappe |
|---|---|---|---|---|
| Màn nhân viên (`/pos`, `/pos/orders`, `/pos/kitchen`, `/pos/customer`, `/pos/status`) | `vite.config.ts` | `src/` (trừ `src/order`) | `../mypos/public/pos/` | `mypos/www/pos.html` |
| Web đặt món QR của khách (`/order/<token>`) | `vite.order.config.ts` | `src/order/` | `../mypos/public/order/` | `mypos/www/mypos_order.html` |

Frappe phục vụ output tại `/assets/mypos/pos/` và `/assets/mypos/order/` (symlink `sites/assets/mypos -> apps/mypos/mypos/public`).
Tên file cố định (`pos.js`, `pos.css`, `order.js`, `order.css`), không hash, để trang `www/*.html` không phải sửa sau mỗi lần build.

## Stack

React 18, TypeScript, Vite 5, react-router-dom 6, zustand, socket.io-client (realtime của Frappe). CSS thuần + CSS variables.

## Build (trong WSL, trên bench)

```bash
cd ~/frappe-bench/apps/mypos/pos
npm install
npm run build          # build cả 2 bundle; build:pos / build:order để build riêng
```

`mypos/public/pos/` và `mypos/public/order/` là **output build** (không commit, xem `.gitignore`), không sửa tay.

## Chạy dev

```bash
npm run dev            # http://localhost:5173, proxy /api -> http://localhost:8000
npm run dev:order      # http://localhost:5174
```

## Route và API

- `website_route_rules` trong `mypos/hooks.py`: `/pos/<path>` → `www/pos.html`, `/order/<path>` → `www/mypos_order.html`.
- `www/pos.py` / `www/mypos_order.py` chèn `window.POS_CONFIG` (gồm `apiBase`, CSRF token).
- API nhân viên: `POST /api/method/mypos.mypos.api.pos_api.<hàm>`; màn khách `...customer_display_api.<hàm>`;
  màn theo dõi đơn `...order_status_api.<hàm>` (dựng từ `apiBase` trong `src/lib/api.ts`).
- API khách QR: `POST /api/method/mypos.mypos.api.customer_order_api.<hàm>` (`src/order/api.ts`).

## Ghi chú

- **Không hardcode thương hiệu**: tên quán / logo đọc từ `Branch` (chi nhánh của POS Profile) qua `get_pos_config`.
- Token màu ở `src/styles/tokens.css` (`--pos-*`), web khách thêm `--qo-*` trong `src/order/order.css`.
- Quy tắc chi tiết từng màn: `../docs/rules/`.
