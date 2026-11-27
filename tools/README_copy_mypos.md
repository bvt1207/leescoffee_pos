# Copy app mypos sang bench (WSL)

> **Quy trình được duyệt: [copy_mypos_steps.md](copy_mypos_steps.md)** (dán tay từng bước, không rsync, không script tự động).
> Script dưới đây giữ để tham khảo, KHÔNG dùng cho lần copy chính thức.

`copy_mypos_to_bench.sh` chép `PROJECTPOS/mypos` (ổ Windows) sang `~/frappe-bench/apps/mypos`. Chạy trong **WSL**; script chỉ
copy file, không chạy lệnh bench / npm nào — cuối cùng in ra các lệnh để bạn tự chạy.

Biến ở đầu script: `SRC`, `DST`, `SITE` (mặc định `local.com`), `BACKUP_DIR` (`~/mypos_backups`).

```bash
cd "/mnt/c/Users/ADMIN/OneDrive/Pictures/Năm 4 UIT/ERPNEXT/PROJECTPOS"
bash tools/copy_mypos_to_bench.sh                 # dry-run (mặc định): file mới / file sẽ bị thay / file chỉ có ở DST
bash tools/copy_mypos_to_bench.sh --diff          # diff -u từng file sẽ bị thay (DST hiện tại -> SRC)
bash tools/copy_mypos_to_bench.sh --diff mypos/hooks.py
bash tools/copy_mypos_to_bench.sh --apply         # hỏi 'yes', sao lưu DST (tar.gz) rồi copy, tự verify, in lệnh tiếp theo
bash tools/copy_mypos_to_bench.sh --verify        # diff -rq SRC DST: phải báo "giống nhau"
bash tools/copy_mypos_to_bench.sh --next          # chỉ in lệnh tiếp theo + checklist (docs/checklist.md)
```

Quy tắc của script:

- Loại trừ: `.git`, `node_modules`, `__pycache__`, `*.pyc`, `.env*`, `*.egg-info`, output build `mypos/public/{pos,order}`, `dist`, `build`.
  `DST/.git` không bị đụng.
- **Không `--delete`**: file đã xóa ở SRC vẫn còn ở DST — dry-run liệt kê ở mục "Chỉ có ở DST" để xóa tay nếu cần.
- File khung do `bench new-app` sinh (pyproject.toml, README.md, license.txt, .gitignore, .editorconfig, .eslintrc,
  .pre-commit-config.yaml, mypos/__init__.py, hooks.py, modules.txt, patches.txt) được in riêng (`!`) — xem bằng `--diff` trước khi `--apply`.
- So nội dung bằng checksum; quyền file đích 755 (thư mục) / 644 (file), không mang quyền 777 / owner của ổ Windows.
- Dừng (không copy) nếu SRC rỗng / không phải gốc app mypos, hoặc DST không phải thư mục app mypos trong `apps/` của bench.
  Cảnh báo nếu SRC có file CRLF hoặc còn chuỗi tên app cũ.

Sau `--apply`: chạy đúng thứ tự lệnh script in ra (backup → requirements → npm build → bench build → install-app nếu chưa cài →
migrate → clear-cache → restart → script tự kiểm → cấu hình tay `docs/install.md` §3 → checklist kiểm tay `docs/checklist.md`).

Khôi phục DST từ bản sao lưu: `tar -xzf ~/mypos_backups/mypos-<thời điểm>.tar.gz -C ~/frappe-bench/apps` (ghi đè lại thư mục `mypos`).
