# App `mypos` (port 2026-11-27) — nơi làm việc từ nay

> Tách nguyên văn từ CLAUDE.md mục 13 ngày 2026-11-27 (CLAUDE.md chỉ còn tham chiếu). Tự động tải mỗi phiên.

- Vị trí: `PROJECTPOS/mypos/` (gốc app: `pyproject.toml`, `mypos/` package, `pos/` frontend, `docs/`, `CLAUDE.md`). Branch git `mypos-port`
  (chưa push). Đẩy GitHub: `git subtree split --prefix=mypos` (`mypos/docs/deploy.md` §6) vì `bench get-app` cần app ở gốc repo.
- Đọc trước khi sửa: `mypos/CLAUDE.md` → `mypos/docs/README.md` (mục lục) → `mypos/docs/rules/*.md`. Các file này là bản hiện hành của
  `.claude/rules/leescoffee_pos/*` (đã đổi đường dẫn `mypos.mypos.*`, module `MYPOS`).
- Khác app cũ (đã duyệt):
  - Không patch cũ; thiết lập ở `mypos/setup/` (`after_install` + `after_migrate`: role + quyền theo `PERMS`, chỉ thêm, lỗi chỉ ghi Error Log).
  - Custom Field fixture có `module = "MYPOS"`; bỏ fixture DocType; `required_apps = ["erpnext"]`; `frappe-dependencies >=16.50,<17`.
  - Sidebar "MYPOS" (DocType `Sidebar`, trùng tên module, không còn `workspace_sidebar` / sidebar rỗng), xếp Admin, Manager, Cashier, Kitchen.
  - Desk dùng màn **Apps**: hook `add_to_apps_screen` + `mypos/permissions.py::has_app_permission`, không khai `route` (vào workspace theo
    role). Desktop Icon chỉ nạp ở chế độ lưới icon (Frappe đang loại bỏ) — giữ file, không dựa vào.
  - Sửa cho ERPNext 16.61: tự mở ca điền `balance_details`; hook `validate` POS Invoice giữ CTKM theo tổng qty khi lưu đơn.
- Kiểm: `bench --site local.com execute mypos.selfcheck.check_everything.check_everything` (23 test: điều kiện nền, 4 chỉ đọc, 2 user tạm,
  16 quán thử `ZZTEST-*`). Điều kiện nền site mới: Setup Wizard (Vietnam / VND) + POS Settings Invoice Type = POS Invoice
  (`mypos/docs/testing.md`, `tools/test_without_data.md`). Kiểm tay: `mypos/docs/checklist.md`.
- Copy sang bench: `tools/copy_mypos_steps.md` (không rsync; cổng dừng ở diff trước khi copy; sao lưu `~/mypos_backups`).
  **Van cho phép (2026-11-27) Claude Code tự chạy các bước copy trong WSL** qua `MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu -- bash <file .sh trong
  tools/_wsl/>` (thư mục bỏ qua trong git), phạm vi: đọc (ls / find / diff / grep / wc / tar -tzf / bench version / list-apps / execute chỉ đọc),
  ghi CHỈ trong `~/frappe-bench/apps/mypos` (cp --no-preserve=mode,ownership, mkdir -p, chmod 755 / 644) và `~/mypos_backups`. CẤM: rm / mv,
  --delete, ghi `.git` của DST, bench migrate / build / restart / install-app / backup, npm, pip, sửa `leescoffee_pos` hoặc `~/frappe-benchver16`.
  Danh sách "sẽ bị thay" ở bước diff chỉ gồm file vừa sửa thì chạy tiếp, có file lạ thì DỪNG.
- Sau mỗi task trên `mypos`: commit (không push), copy theo quy trình trên, đưa Van lệnh bench cần chạy (restart nếu đổi Python / hooks,
  migrate nếu đổi DocType / fixtures / workspace / sidebar) + lệnh `check_everything`; cập nhật `mypos/docs` cùng commit.
