# Phát hành app `mypos` lên GitHub (repo riêng, public)

Repo phát triển `PROJECTPOS` (remote `origin`, repo private, có `.claude/`, `tools/`, code cũ) **giữ Private, không đụng**. App được
tách bằng `git subtree split --prefix=mypos` thành nhánh `mypos-release` (gốc = nội dung thư mục `mypos/`) rồi push lên repo mới
`bvt1207/mypos`.

Chạy ở đâu:
- **PowerShell / Git Bash trên Windows** (thư mục `PROJECTPOS`): mọi lệnh `git` có push (Git Credential Manager lo đăng nhập GitHub).
- **WSL**: kiểm bằng clone tạm, cài thử bằng `bench`.

Đã thử trước (bản clone tạm, 2026-11-27): split ra **25 commit, 209 file**, `pyproject.toml` ở gốc, không còn tên app cũ trong file
lẫn commit message.

---

## 0. Chuẩn bị

1. Duyệt báo cáo kiểm tra trước khi công khai (email, tài sản hình ảnh, docs công khai) và để các sửa đổi được commit.
2. ```powershell
   cd "C:\Users\ADMIN\OneDrive\Pictures\Năm 4 UIT\ERPNEXT\PROJECTPOS"
   git status            # sạch
   git branch --show-current   # mypos-port
   git log --oneline -3
   ```

**Xong khi:** `git status` sạch, commit cuối là bản đã duyệt. **Nếu sai:** thay đổi chưa commit không vào bản phát hành; split từ code
chưa duyệt sẽ công khai nó.

## 1. Tạo repo GitHub (web, Private trước)

1. github.com → **New repository**: Owner `bvt1207`, tên **`mypos`**, **Private**.
2. **Không** tick "Add a README", ".gitignore", "license" (app đã có; tick sẽ tạo commit lệch, push bị từ chối).
3. Description (đề xuất): `POS for coffee shop chains on Frappe / ERPNext v16 — counter sales, kitchen screen, table cards, QR ordering, order status board`.

**Xong khi:** repo trống, trang hiện "Quick setup". **Nếu sai** (đã tick README): xóa repo, tạo lại.

## 2. Tách nhánh và kiểm (Git Bash hoặc WSL)

```bash
cd "/c/Users/ADMIN/OneDrive/Pictures/Năm 4 UIT/ERPNEXT/PROJECTPOS"      # WSL: /mnt/c/Users/ADMIN/OneDrive/...
git subtree split --prefix=mypos -b mypos-release                       # tạo / cập nhật branch local mypos-release

rm -rf /tmp/mypos-check && git clone --quiet --branch mypos-release --single-branch . /tmp/mypos-check
cd /tmp/mypos-check
ls                                            # pyproject.toml README.md license.txt CLAUDE.md docs mypos pos ...
git log --oneline | wc -l                     # >= 25 (thêm commit mới thì lớn hơn)
git ls-files | wc -l                          # 209 (+ file mới thêm sau này)
grep -n '^name\|^license' pyproject.toml      # name = "mypos", license = { text = "MIT" }
grep -n '^app_name\|^required_apps' mypos/hooks.py
grep -rliE 'lee[s]coffee' . || echo "sạch: tên cũ"
grep -rnIE 'C:\\Users|/home/[a-z]|OneDrive|\.claude/|sepay_webhook_secret\s*=\s*.[A-Za-z0-9]' --exclude-dir=.git . || echo "sạch: đường dẫn / khóa"
git log --format='%an <%ae>' | sort -u        # email sẽ hiện công khai trên mọi commit
git ls-files | grep -iE 'node_modules|__pycache__|\.env|public/pos/|public/order/' || echo "sạch: build / secret"
```

**Xong khi:** mọi dòng "sạch", số commit / file như trên, email đúng như đã chọn. **Nếu sai:** KHÔNG push; sửa trong repo phát triển,
commit, chạy lại bước 2 (split tự cập nhật nhánh).

## 3. Push lên repo (PowerShell / Git Bash trên Windows)

```powershell
git remote add mypos https://github.com/bvt1207/mypos.git     # chỉ lần đầu; kiểm: git remote -v
git push mypos mypos-release:main
git push mypos mypos-release:version-16
```

Lần đầu Git Credential Manager mở trình duyệt để đăng nhập GitHub. Trên web: Settings → General → **Default branch = `main`**.

Kiểm trên web: cây thư mục có `pyproject.toml`, `mypos/`, `pos/`, `docs/` ở gốc; README hiển thị; ô "License" bên phải hiện **MIT**;
tab Branches có `main` và `version-16`.

**Xong khi:** hai nhánh trỏ cùng commit với `mypos-release` (`git ls-remote mypos`). **Nếu sai:** push nhầm nhánh khác (vd. `mypos-port`)
sẽ đưa code cũ + `.claude/` lên → xóa repo, tạo lại (repo vẫn Private nên chưa lộ).

## 4. Chuyển Public và hoàn thiện trang repo

1. Rà lại lần cuối: Code, commit history (email), Releases, Actions (không có secret).
2. Settings → General → Danger Zone → **Change visibility → Public**.
3. About (bánh răng bên phải): Description như bước 1; Website: để trống hoặc trang tài liệu nếu có; Topics:
   `frappe`, `erpnext`, `frappe-app`, `pos`, `point-of-sale`, `restaurant`, `coffee-shop`, `fnb`, `vietqr`.
4. Tùy chọn — tag / Release v0.1.0 (PowerShell):
   ```powershell
   git tag -a v0.1.0 mypos-release -m "MYPOS 0.1.0 — Frappe / ERPNext 16.x"
   git push mypos v0.1.0
   ```
   Rồi trên web: Releases → Draft a new release → chọn tag `v0.1.0`.

**Xong khi:** mở repo ở cửa sổ ẩn danh (không đăng nhập) thấy được. **Nếu sai:** thấy thông tin nhạy cảm → mục 7 ngay.

## 5. Cài thử ở máy khác (WSL, bench trắng, HTTPS)

```bash
cd ~/frappe-bench                                   # bench trắng có frappe + erpnext 16.x, site <site> đã qua Setup Wizard
bench get-app https://github.com/bvt1207/mypos.git --branch version-16
bench --site <site> install-app mypos
bench --site <site> migrate
cd apps/mypos/pos && npm install && npm run build && cd ~/frappe-bench
bench build --app mypos
bench start                                         # terminal khác: các lệnh dưới
bench --site <site> execute mypos.selfcheck.prereq_check.check_prereq
bench --site <site> execute mypos.selfcheck.check_everything.check_everything --kwargs "{'include_write': False}"
```

| Kiểm | Mong đợi |
|---|---|
| `bench get-app` | Clone không hỏi mật khẩu (repo public) |
| `prereq_check` | Liệt kê mục THIẾU kèm cách tạo; thường cần POS Settings → Invoice Type = POS Invoice |
| `check_everything` (include_write False) | prereq + 4 chỉ đọc + 2 user tạm: PASS (apps_screen_check có thể SKIP role chưa có user) |
| Sau khi đủ điều kiện nền, `check_everything` đầy đủ | 23/23 PASS |

**Nếu sai:** `get-app` lỗi "not a valid app" → repo thiếu `pyproject.toml` ở gốc (push nhầm nhánh). Thiếu file / lỗi import → so số file với bước 2.

## 6. Cập nhật về sau

1. Sửa và commit trong repo phát triển (`PROJECTPOS/mypos/...`) như bình thường; KHÔNG sửa trực tiếp trên GitHub (nhánh split sẽ lệch).
2. ```powershell
   git subtree split --prefix=mypos -b mypos-release
   git push mypos mypos-release:main
   git push mypos mypos-release:version-16
   ```
   (Tăng `__version__` trong `mypos/mypos/__init__.py` và tag mới nếu phát hành bản mới.)
3. Bench cài từ GitHub: `bench update --app mypos` (hoặc `cd apps/mypos && git pull`), rồi `npm run build` trong `apps/mypos/pos`,
   `bench build --app mypos`, `bench --site <site> migrate`, khởi động lại bench.
4. Bench DEV hiện tại (`~/frappe-bench/apps/mypos` có `.git` riêng của `bench new-app`): tiếp tục quy trình copy `tools/copy_mypos_steps.md`;
   không trộn `git pull` với copy trên cùng thư mục.

## 7. Lỡ công khai thông tin nhạy cảm

1. **Ngay:** Settings → Change visibility → **Private** (hoặc xóa repo nếu cần chắc chắn).
2. **Thu hồi** mọi khóa / token lộ: SePay API key (đổi trên SePay + Branch), GitHub token, mật khẩu — coi như đã bị lấy, kể cả khi đã xóa.
3. Xóa khỏi lịch sử (viết lại lịch sử repo phát hành + repo phát triển, force-push) chỉ giảm phạm vi: **bản fork, clone và cache đã có thì
   không thu hồi được**; GitHub có thể giữ commit cũ qua đường dẫn SHA cho tới khi liên hệ hỗ trợ xóa.
4. Ghi lại sự cố; thêm mẫu tương ứng vào bước 2 để chặn lần sau.
