# Triển khai — MYPOS

> Tạo 2026-11-25. Số liệu template đã đọc từ bench CLI đang cài trên máy DEV (pipx `frappe-bench`, `bench/config/templates`)
> và Frappe v16.30. Phần không đọc được ghi [Unverified] / [Inference].

## 1. Triển khai thật: socket.io, nginx, gunicorn

### 1.1 Tiến trình (supervisor / systemd)

`sudo bench setup production <user>` sinh cấu hình supervisor (hoặc systemd) + nginx. Các tiến trình cần chạy:

| Tiến trình | Lệnh | Vai trò cho MYPOS |
|---|---|---|
| web | `gunicorn -b 127.0.0.1:<webserver_port> -w <gunicorn_workers> --max-requests … -t <http_timeout> --preload frappe.app:application` | mọi API `/api/method/...` |
| socketio | `node apps/frappe/socketio.js` (cổng `socketio_port`, mặc định 9000) | realtime (màn khách; giai đoạn 3 cho Pha chế / Orders) |
| worker(s) | `bench worker` | job nền (webhook không dùng; email, export…) |
| schedule | `bench schedule` | job `order_cancel.auto_cancel_stale_drafts` mỗi 5 phút |
| redis_cache, redis_queue | `redis-server config/redis_*.conf` | cache + **phiên bản thay đổi** (`mypos_chg:*`) + pub/sub realtime |

- `gunicorn_workers` mặc định = `số CPU × 2 + 1` (bench `get_gunicorn_workers`). Worker đồng bộ (sync): một request một lúc.
  DEV đang có `gunicorn_workers: 33` trong `common_site_config.json` nhưng DEV chạy `bench serve` (werkzeug) nên không dùng giá trị này.
- [Inference] Mỗi request API nặng ~20–40 ms CPU (đo thật bằng `mypos/selfcheck/poll_load_check.py` mục 8). Máy 4 vCPU ~100–200 request/giây.
  Trước khi giảm tải: ~1,6 request/giây/cửa hàng (ngưỡng ~40–60 cửa hàng / máy 4 vCPU). Sau giai đoạn 1 + 2 phần lớn request poll chỉ đọc Redis.

### 1.2 nginx

Template của bench (đã đọc) có sẵn:

```nginx
location /socket.io {
	proxy_http_version 1.1;
	proxy_set_header Upgrade $http_upgrade;
	proxy_set_header Connection "upgrade";
	proxy_set_header X-Frappe-Site-Name {{ site_name }};
	proxy_set_header Origin $scheme://$http_host;
	proxy_set_header Host $host;
	proxy_pass http://{{ bench_name }}-socketio-server;
}
```

- Có `gzip on` cho `application/json`, `application/javascript`, `text/css`… → phản hồi API được nén (DEV `bench serve` không nén).
- Production KHÔNG có `DEV_SERVER` → `www/pos.py` gửi `realtime.devServer = 0` → client socket.io nối **cùng origin** (`https://<domain>/socket.io`),
  không cần mở cổng 9000 ra ngoài.
- HTTPS: `sudo bench setup lets-encrypt <site>` (hoặc chứng chỉ riêng) → socket chạy WSS qua cùng `location /socket.io`.
- Socket xác thực: hostname `Origin` phải trùng `Host` (`realtime/middlewares/authenticate.js`) và cần cookie `sid` → đặt site theo domain thật
  (`bench setup add-domain` / tên site = domain), không truy cập bằng IP khác domain.

### 1.3 Redis

- `redis_socketio` (v16: thường trỏ cùng `redis_cache`) phải là Redis mà tiến trình web publish vào — `bench setup redis` sinh đúng.
- Khóa `mypos_chg:*` không TTL; mất (restart Redis không persist) → client tự tải lại (`docs/rules/realtime.md` §1).
- [Unverified] Chính sách `maxmemory` của `redis_cache.conf` trên máy thật: nếu đặt LRU và bộ nhớ đầy, khóa có thể bị đẩy ra — vẫn an toàn
  (khởi tạo lại số ngẫu nhiên) nhưng gây một lượt tải lại.

### 1.4 Kiểm sau khi triển khai

1. `sudo supervisorctl status` → web, socketio, worker, schedule, redis đều RUNNING.
2. `curl -s "https://<domain>/socket.io/?EIO=4&transport=polling"` → bắt đầu `0{"sid":`.
3. Mở `/pos/customer` → DevTools Network → WS: `101 Switching Protocols`, không có request socket.io màu đỏ.
4. `bench --site <site> console`: `check_poll_load(...)` PASS; ghi số ms / SQL mục 8 để so với DEV.
5. Tắt tạm socketio (`supervisorctl stop <bench>-node-socketio`) → Pha chế vẫn nhận đơn mới trong ≤ 5 giây (poll phiên bản 4 giây) → bật lại.

## 2. DEV (WSL2, `bench start`)

- socket.io nghe `::9001`; Windows chỉ tới được qua `localhost:9001` / `[::1]:9001`, **không** qua `127.0.0.1:9001` → mở site bằng
  `http://localhost:8001` (chi tiết `docs/rules/realtime.md` §6).

## 3. Link trong mã QR đặt món (`/order/<token>`) và `host_name`

- Link dựng ở MỘT nơi: `doctype/mypos_order_qr/mypos_order_qr.py::build_order_url(token)` = `frappe.utils.get_url("/order/" + token)`.
  Không có chuỗi ghi cứng localhost / IP / cổng (đã kiểm 2026-11-25).
- `get_url()` (Frappe v16.30, đã đọc mã): dùng `host_name` (hoặc `hostname`) trong `site_config.json` nếu có; không có thì lấy host của
  request đang chạy (trình duyệt đang mở Desk bằng địa chỉ nào thì link theo địa chỉ đó); ngoài request thì `http://<tên site>`.
- Hai chỗ dùng link:
  - Field `order_url` trên form: ghi khi **lưu** bản ghi `MYPOS Order QR` (giá trị lúc lưu, có thể cũ).
  - Nút **"In mã QR"** (`get_qr_image`): dựng lại link **lúc in** → luôn theo `host_name` / host hiện tại.
- DEV hiện tại: chưa đặt `host_name` → link = host mở Desk, ví dụ `http://localhost:8001/order/<token>` (mở Desk bằng `localhost:8001`)
  hoặc `http://127.0.0.1:8001/order/<token>`. Điện thoại KHÔNG mở được link localhost / 127.0.0.1.

| Môi trường | Lệnh đặt `host_name` | Ghi chú |
|---|---|---|
| DEV, chỉ test trên máy | `bench --site local.com set-config host_name "http://localhost:8001"` | Ghi cả cổng |
| DEV, quét bằng điện thoại cùng wifi | `bench --site local.com set-config host_name "http://<IP LAN của máy Windows>:8001"` | [Unverified] WSL2 chế độ NAT: điện thoại vào IP LAN của Windows cần `netsh interface portproxy` tới IP WSL + mở firewall cổng 8001 (hoặc `networkingMode=mirrored`). IP LAN đổi → đặt lại |
| UAT | `bench --site <site> set-config host_name "https://uat.<tên miền>"` | |
| Production | `bench --site <site> set-config host_name "https://<tên miền>"` | HTTPS + tên miền thật (nginx, `bench setup lets-encrypt`) |

- Đổi `host_name` xong: `bench --site <site> clear-cache` → mở từng `MYPOS Order QR` → **Save** (cập nhật `order_url`) và **In mã QR lại**,
  dán lại mã mới tại quán. Mã đã in theo host cũ vẫn trỏ host cũ (token không đổi, chỉ đổi phần địa chỉ).
- Không đổi token khi chỉ đổi host; muốn thu hồi mã: bỏ chọn `enabled` và tạo mã mới.

## 4. Treo TV màn theo dõi đơn (`/pos/status`, 2026-11-27)

Màn chỉ đọc cho khách nhìn: "Đang chuẩn bị" / "Sẵn sàng nhận món" (`docs/rules/order_status.md`).

**Tài khoản**
- Tạo User riêng cho TV (vd. "TV quầy <chi nhánh>"), role **chỉ** `POS KITCHEN`, thêm vào **Applicable for Users** của POS Profile chi nhánh
  (`default = 1`). Không gán role khác.
- Mật khẩu mạnh; chỉ đăng nhập trên trình duyệt của TV; không dùng chung cho người pha chế / thu ngân.
- Lưu ý: về kỹ thuật tài khoản POS KITCHEN vẫn gọi được API chuyển trạng thái "Chưa làm → Đã làm" (màn TV không có nút nào, nhưng ai có
  mật khẩu vẫn mở được `/pos/kitchen`). Đây **chưa phải tài khoản chỉ đọc tuyệt đối**; role POS DISPLAY chỉ xem là việc tồn đọng.

**Trình duyệt (Chrome / Edge trên mini PC / TV box)**
1. Đăng nhập Desk bằng tài khoản TV một lần (cookie phiên được nhớ), mở `https://<tên miền>/pos/status`.
   DEV: `http://localhost:8001/pos/status` (không dùng `127.0.0.1`, `realtime.md` §6).
2. Toàn màn hình: nhấn **F11** (thoát: F11). Con trỏ tự ẩn sau 3 giây không di chuột.
3. Hoặc chế độ kiosk (tự toàn màn hình, không thanh địa chỉ; thoát bằng Alt+F4):
   `chrome.exe --kiosk --noerrdialogs --disable-session-crashed-bubble https://<tên miền>/pos/status`
4. Tự mở lại khi khởi động máy:
   - Windows: tạo shortcut với lệnh ở bước 3, đặt vào `shell:startup` (Win+R → `shell:startup`).
   - Linux (mini PC): file `~/.config/autostart/pos-status.desktop` với `Exec=chromium --kiosk https://<tên miền>/pos/status`.
   - Tắt chế độ ngủ / tắt màn hình của hệ điều hành; tắt cập nhật tự khởi động lại giờ mở cửa.
5. Phiên đăng nhập Frappe hết hạn (mặc định theo "Session Expiry" của System Settings) → màn hiện lỗi đăng nhập: đăng nhập lại.
   [Unverified] Nếu hay hết hạn, tăng Session Expiry cho site hoặc đăng nhập lại mỗi sáng.

**Kiểm**
- Chấm góc phải: xanh = cập nhật trực tiếp (socket), vàng = cập nhật định kỳ 4 giây (không có socket) hoặc lỗi tạm, đỏ = mất kết nối ≥ 30 giây
  (danh sách vẫn giữ bản cuối). Đổi trạng thái ở màn Pha chế → TV đổi trong ≤ 1 giây khi có socket, ≤ 5 giây khi không.

## 5. Sidebar MYPOS và workspace theo role (kiểm sau cài / sau migrate)

### 5.1 Kiểm

```bash
bench --site local.com execute mypos.selfcheck.sidebar_check.check_sidebar
bench --site local.com execute mypos.selfcheck.desktop_icon_check.check_desktop_icons
bench --site local.com execute mypos.selfcheck.workspace_shortcut_check.check_workspace_shortcuts
```

Kiểm tay (mỗi tài khoản: cửa sổ ẩn danh, đăng nhập lại; user test KHÔNG có role `Workspace Manager`):

| Tài khoản | Thấy workspace / Desktop Icon | Sidebar MYPOS | PASS / FAIL |
|---|---|---|---|
| Administrator | Cashier, Kitchen, Manager, Admin | 4 mục, không có mục DocType lẻ | |
| POS MANAGER | Manager | chỉ Manager | |
| POS CASHIER | Cashier | chỉ Cashier | |
| POS KITCHEN | Kitchen (icon mở `/pos/kitchen`) | chỉ Kitchen | |

Mục thừa cần để ý: MYPOS Option Group, MYPOS Order QR, MYPOS Menu (hoặc DocType bất kỳ) xuất hiện trực tiếp trong sidebar MYPOS.

### 5.2 Dự phòng: 16.61 vẫn sinh mục thừa hoặc không nạp Sidebar từ file

Cho Frappe tự xuất file chuẩn rồi lấy file đó làm bản chuẩn của repo:

1. `bench --site local.com set-config developer_mode 1` → `bench --site local.com clear-cache` → khởi động lại bench.
2. Desk → Sidebar (`/desk/sidebar`): nếu đã có "MYPOS" thì mở, không thì New: Title `MYPOS`, Module `MYPOS`, Header Icon `milestone`,
   Standard bật, 4 dòng Link → Workspace: Cashier / MYPOS Cashier / receipt, Kitchen / MYPOS Kitchen / computer,
   Manager / MYPOS Manager / chart, Admin / MYPOS Admin / settings. Save.
   Xóa (hoặc ghi lại tên) mọi Sidebar khác có Module = MYPOS.
3. Frappe ghi file vào `apps/mypos/mypos/mypos/sidebar/mypos/mypos.json` (developer_mode + standard). Kiểm: `git -C apps/mypos diff`.
4. Copy file đó về repo (`PROJECTPOS/mypos/mypos/mypos/sidebar/mypos/mypos.json`), commit; ghi lại khác biệt so với bản cũ.
5. Tắt lại: `bench --site local.com set-config developer_mode 0`, clear-cache, khởi động lại; chạy lại §5.1.

## 6. Phát hành lên GitHub (`bench get-app` cần app ở GỐC repo)

Repo phát triển có app ở thư mục con `mypos/`. Tách lịch sử thư mục đó thành một nhánh riêng có app ở gốc:

```bash
cd <repo phát triển>
git subtree split --prefix=mypos -b mypos-release     # nhánh mới, gốc = nội dung thư mục mypos/

# Kiểm nhánh split trong thư mục tạm
rm -rf /tmp/mypos-check && git clone --branch mypos-release --single-branch . /tmp/mypos-check
ls /tmp/mypos-check                                   # có pyproject.toml, README.md, mypos/, pos/, docs/ ở GỐC
grep -n '^name' /tmp/mypos-check/pyproject.toml       # name = "mypos"
grep -n '^app_name\|^required_apps\|^after_install\|^after_migrate' /tmp/mypos-check/mypos/hooks.py
cat /tmp/mypos-check/mypos/modules.txt                # MYPOS
ls /tmp/mypos-check/mypos/mypos                       # api doctype sidebar workspace ...
ls /tmp/mypos-check/mypos/{fixtures,setup,selfcheck,desktop_icon,www}
grep -rliE 'lee[s]coffee' /tmp/mypos-check || echo "sạch"   # [s]: dòng này không tự khớp
```

Tạo repo GitHub (rỗng, không README / license / .gitignore) rồi đẩy nhánh split thành `main` (và `version-16` nếu dùng `--branch version-16`):

```bash
gh repo create <owner>/mypos --private          # hoặc tạo trên web
git push git@github.com:<owner>/mypos.git mypos-release:main
git push git@github.com:<owner>/mypos.git mypos-release:version-16
```

Lần sau: chạy lại `git subtree split --prefix=mypos -b mypos-release` (cập nhật nhánh) rồi push như trên.
Bench: `bench get-app git@github.com:<owner>/mypos.git --branch main` (repo private cần SSH key / token trên máy bench).
