# Copy app mypos sang bench (WSL)

Quy trình: **[copy_mypos_steps.md](copy_mypos_steps.md)** — các khối lệnh bash chạy tuần tự trong WSL (Ubuntu), không rsync,
không script tự động, có điểm DỪNG để kiểm trước khi đi tiếp.

- SRC: `/mnt/c/Users/ADMIN/OneDrive/Pictures/Năm 4 UIT/ERPNEXT/PROJECTPOS/mypos`
- DST: `~/frappe-bench/apps/mypos` (app mypos của bench mới, site `local.com`)
- Sao lưu DST trước khi copy: `~/mypos_backups/mypos-<thời điểm>.tar.gz`

Tóm tắt các bước: 0 kiểm tra trước (đếm file, CRLF, tên cũ) → 1 sao lưu DST → 2 `mkdir -p` thư mục → 3 diff trước khi copy
(mới / sẽ bị thay / chỉ có ở DST + `diff -u` file khung) → 4 `cp --no-preserve=mode,ownership` theo 9 nhóm → 5 diff sau, đếm file,
quyền 755 / 644 → 6 lệnh bench / npm (người vận hành tự chạy) + selfcheck + checklist `docs/checklist.md`.

Quy tắc: không xóa / di chuyển file ở DST (file chỉ có ở DST được liệt kê để quyết định tay), không đụng `DST/.git`, không ghi ngoài
DST và `~/mypos_backups`.

`tools/_wsl/` (bỏ qua trong git): file bash tạm khi chạy các bước qua `wsl.exe`.
