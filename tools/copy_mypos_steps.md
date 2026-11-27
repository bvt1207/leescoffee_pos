# Copy app mypos sang bench — từng bước, dán tay trong WSL

Quy trình copy được duyệt: **không rsync, không script tự động**. Mỗi khối dán vào CÙNG một terminal WSL, theo thứ tự,
đọc kết quả rồi mới sang khối sau. Dòng `# DỪNG` = kiểm tra kết quả trước khi đi tiếp.

Kỳ vọng ở thời điểm viết (branch `mypos-port`): SRC có **203 file** (không tính `node_modules`, `__pycache__`, output build
`mypos/public/{pos,order}`), 9 nhóm: gốc app 9, docs 18, pos 77, package gốc 4, setup/fixtures/selfcheck/patches/config/templates 30,
desktop_icon 4, public/www 10, module api/doctype 46, workspace/sidebar 5.

---

## Bước 0 — Kiểm tra trước (chỉ đọc)

```bash
SRC="/mnt/c/Users/ADMIN/OneDrive/Pictures/Năm 4 UIT/ERPNEXT/PROJECTPOS/mypos"
DST="$HOME/frappe-bench/apps/mypos"
SITE="local.com"
W=/tmp/mypos_copy; mkdir -p "$W"

# Danh sách file của app (đường tương đối, đã sắp xếp), bỏ .git / node_modules / __pycache__ / *.pyc / .env / *.egg-info / build
mypos_files() {
  (cd "$1" && find . \( -name .git -o -name node_modules -o -name __pycache__ -o -name '*.egg-info' \
      -o -path ./mypos/public/pos -o -path ./mypos/public/order -o -path ./dist -o -path ./build \) -prune \
      -o -type f ! -name '*.pyc' ! -name '.env' ! -name '.env.*' -print | sed 's#^\./##' | LC_ALL=C sort)
}

# Đúng thư mục app mypos?
grep -n '^app_name = "mypos"' "$SRC/mypos/hooks.py" && grep -n '^name = "mypos"' "$SRC/pyproject.toml" && echo "SRC OK"
grep -n '^app_name = "mypos"' "$DST/mypos/hooks.py" && grep -n '^name = "mypos"' "$DST/pyproject.toml" && echo "DST OK"
ls -d "$DST/.git" 2>/dev/null && echo "DST/.git có sẵn — sẽ KHÔNG đụng"

# Đếm file
mypos_files "$SRC" > "$W/src.txt"; mypos_files "$DST" > "$W/dst.txt"
wc -l "$W/src.txt" "$W/dst.txt"                           # SRC kỳ vọng 203

# Dò CRLF trong SRC (kỳ vọng: không in gì)
(cd "$SRC" && tr '\n' '\0' < "$W/src.txt" | xargs -0 grep -Il $'\r') || echo "Không có file CRLF"

# Dò tên app cũ (kỳ vọng: "sạch")
(cd "$SRC" && tr '\n' '\0' < "$W/src.txt" | xargs -0 grep -IliE 'lee[s]coffee') || echo "sạch"
```

`# DỪNG`: SRC OK + DST OK; SRC = 203 file; không có file CRLF; "sạch". Sai bất kỳ ý nào → không đi tiếp, gửi output.

---

## Bước 1 — Sao lưu DST (tar.gz)

```bash
mkdir -p "$HOME/mypos_backups"
BK="$HOME/mypos_backups/mypos-$(date +%Y%m%d-%H%M%S).tar.gz"
tar -czf "$BK" -C "$HOME/frappe-bench/apps" --exclude=node_modules mypos && ls -lh "$BK"
tar -tzf "$BK" | head -5                                  # kiểm đọc được
```

Khôi phục khi cần: `tar -xzf "$BK" -C "$HOME/frappe-bench/apps"` (ghi đè lại thư mục `mypos`).

---

## Bước 2 — Tạo thư mục (bạn tự chạy `mkdir -p`)

```bash
cd "$DST" && mkdir -p \
  docs docs/rules \
  mypos mypos/config mypos/desktop_icon mypos/fixtures mypos/patches mypos/selfcheck mypos/setup \
  mypos/public mypos/public/images mypos/public/js mypos/templates mypos/templates/pages mypos/www \
  mypos/mypos mypos/mypos/api mypos/mypos/sidebar/mypos \
  mypos/mypos/doctype/branch_config mypos/mypos/doctype/mypos_banner mypos/mypos/doctype/mypos_buzzer \
  mypos/mypos/doctype/mypos_menu mypos/mypos/doctype/mypos_menu_item mypos/mypos/doctype/mypos_option_group \
  mypos/mypos/doctype/mypos_option_target mypos/mypos/doctype/mypos_option_value mypos/mypos/doctype/mypos_order_qr \
  mypos/mypos/doctype/pos_invoice_hooks mypos/mypos/doctype/pos_profile_hooks mypos/mypos/doctype/pos_shift_hooks \
  mypos/mypos/doctype/sepay \
  mypos/mypos/workspace/mypos_admin mypos/mypos/workspace/mypos_cashier mypos/mypos/workspace/mypos_kitchen \
  mypos/mypos/workspace/mypos_manager \
  pos pos/public pos/src pos/src/components pos/src/components/customer pos/src/components/status pos/src/lib \
  pos/src/order pos/src/order/components pos/src/pages pos/src/store pos/src/styles

# Kiểm: mọi thư mục cha của file SRC đã có ở DST (kỳ vọng: không in gì)
sed 's#/[^/]*$##' "$W/src.txt" | grep / | sort -u | while IFS= read -r d; do [ -d "$DST/$d" ] || echo "THIẾU: $d"; done
cd ~
```

---

## Bước 3 — Diff TRƯỚC khi copy (3 danh sách + diff file khung)

```bash
LC_ALL=C comm -23 "$W/src.txt" "$W/dst.txt" > "$W/new.txt"          # chỉ có ở SRC -> MỚI
LC_ALL=C comm -13 "$W/src.txt" "$W/dst.txt" > "$W/only_dst.txt"     # chỉ có ở DST -> không bị đụng
LC_ALL=C comm -12 "$W/src.txt" "$W/dst.txt" | while IFS= read -r f; do
  cmp -s "$SRC/$f" "$DST/$f" || echo "$f"
done > "$W/changed.txt"                                               # có ở cả hai, khác nội dung -> SẼ BỊ THAY
wc -l "$W/new.txt" "$W/changed.txt" "$W/only_dst.txt"
echo "== SẼ BỊ THAY";   cat "$W/changed.txt"
echo "== CHỈ CÓ Ở DST"; cat "$W/only_dst.txt"
echo "== MỚI (20 dòng đầu)"; head -20 "$W/new.txt"

# diff -u từng file khung do bench new-app sinh (--- DST hiện tại / +++ SRC sẽ chép sang)
for f in pyproject.toml README.md license.txt .gitignore .editorconfig .eslintrc .pre-commit-config.yaml \
         mypos/__init__.py mypos/hooks.py mypos/modules.txt mypos/patches.txt; do
  echo "=================== $f"
  if [ -f "$DST/$f" ]; then diff -u --label "DST/$f" --label "SRC/$f" "$DST/$f" "$SRC/$f" && echo "(giống nhau)"; else echo "(DST chưa có)"; fi
done 2>&1 | less -R
```

`# DỪNG`: đọc "SẼ BỊ THAY" (chỉ nên là file khung + file app đã đổi) và "CHỈ CÓ Ở DST" (file DST có mà SRC không — quyết định
xóa tay hay giữ). `pyproject.toml` nằm trong "SẼ BỊ THAY" → nhớ `bench setup requirements` ở bước 6.

---

## Bước 4 — Copy theo nhóm

`cp --no-preserve=mode,ownership`: file đích nhận quyền mặc định (644), không mang 777 / owner của ổ Windows. Chỉ chép file trong
`$W/src.txt` (không có `.git`, `node_modules`, build) → `DST/.git` không bị đụng. Thứ tự nhóm không quan trọng; mỗi nhóm in số file.

```bash
copy_group() {   # $1 = nhãn, $2 = regex đường tương đối
  local n=0
  while IFS= read -r f; do
    cp --no-preserve=mode,ownership "$SRC/$f" "$DST/$f" && n=$((n+1))
  done < <(grep -E "$2" "$W/src.txt")
  echo "$1: $n file"
}
copy_group "1 gốc app"                '^[^/]+$'
copy_group "2 docs"                   '^docs/'
copy_group "3 pos (frontend)"         '^pos/'
copy_group "4 package gốc"            '^mypos/[^/]+$'
copy_group "5 setup/fixtures/selfcheck/patches/config/templates" '^mypos/(setup|fixtures|selfcheck|patches|config|templates)/'
copy_group "6 desktop_icon"           '^mypos/desktop_icon/'
copy_group "7 public/www"             '^mypos/(public|www)/'
copy_group "8 module api/doctype"     '^mypos/mypos/([^/]+$|api/|doctype/)'
copy_group "9 workspace/sidebar"      '^mypos/mypos/(workspace|sidebar)/'
```

Kỳ vọng: 9 / 18 / 77 / 4 / 30 / 4 / 10 / 46 / 5 (tổng 203). Có dòng `cp: ...` lỗi → dừng, gửi output.

---

## Bước 5 — Diff SAU (phải rỗng), đếm file, chuẩn hóa quyền

```bash
# Mọi file SRC đã giống hệt ở DST (kỳ vọng: không in gì)
while IFS= read -r f; do cmp -s "$SRC/$f" "$DST/$f" || echo "KHÁC: $f"; done < "$W/src.txt"

# diff -rq toàn cây, bỏ .git / node_modules / __pycache__ / build (kỳ vọng: chỉ còn các dòng "Only in $DST" đã thấy ở bước 3)
diff -rq --exclude=.git --exclude=node_modules --exclude=__pycache__ --exclude='*.pyc' --exclude='*.egg-info' "$SRC" "$DST" \
  | grep -Ev '/mypos/public(/(pos|order)(/| |$)|: (pos|order)$)'

# Đếm
mypos_files "$DST" > "$W/dst_after.txt"
LC_ALL=C comm -23 "$W/src.txt" "$W/dst_after.txt" | wc -l             # kỳ vọng 0 (không thiếu file)
wc -l "$W/src.txt" "$W/dst_after.txt"                                # DST = 203 + số dòng only_dst

# Chuẩn hóa quyền (bỏ qua .git và node_modules): thư mục 755, file 644
find "$DST" \( -path "$DST/.git" -o -name node_modules \) -prune -o -type d -exec chmod 755 {} +
find "$DST" \( -path "$DST/.git" -o -name node_modules \) -prune -o -type f -exec chmod 644 {} +

# CRLF ở DST (kỳ vọng: không in gì)
(cd "$DST" && tr '\n' '\0' < "$W/src.txt" | xargs -0 grep -Il $'\r') || echo "Không có file CRLF"
```

`# DỪNG`: dòng "KHÁC:" = 0, thiếu file = 0, không CRLF.

---

## Bước 6 — Lệnh tiếp theo (theo thứ tự)

> ⛔ **ĐIỂM DỪNG — CHƯA MIGRATE cho tới khi xác nhận Desktop Icon.** Ba điểm chưa đối chiếu mã: `get_app_level_files("desktop_icon", app)`
> trỏ vào đâu, điều kiện của `is_desktop_icons_page()`, và icon mẫu của ERPNext 16.61. Chạy các lệnh chỉ đọc dưới đây, gửi output,
> chờ xác nhận rồi mới chạy 6.4 trở đi (6.1–6.3 làm trước được).

```bash
cd ~/frappe-bench/apps/frappe
grep -rn "def get_app_level_files\|def get_app_level_directory_path" -A15 frappe --include=*.py
grep -rn "def is_desktop_icons_page" -A25 frappe --include=*.py
cd ~/frappe-bench/apps/erpnext
ls erpnext/desktop_icon | head -20
python3 - <<'EOF'
import json, glob, collections
c = collections.Counter()
for f in glob.glob("erpnext/desktop_icon/*.json"):
    d = json.load(open(f))
    c[(d.get("icon_type"), d.get("link_type"), bool(d.get("link")), bool(d.get("link_to")), bool(d.get("sidebar")), bool(d.get("parent_icon")))] += 1
for k, v in c.most_common(): print(v, "icon_type, link_type, link?, link_to?, sidebar?, parent_icon? =", k)
f = sorted(glob.glob("erpnext/desktop_icon/*.json"))[0]; print(f); print(open(f).read())
EOF
cd ~/frappe-bench
```

```bash
cd ~/frappe-bench
# 6.1 Sao lưu site
bench --site local.com backup --with-files

# 6.2 Python requirements (CẦN nếu pyproject.toml nằm trong "SẼ BỊ THAY" ở bước 3)
bench setup requirements

# 6.3 Build frontend (lỗi thiếu gói nhị phân esbuild / rollup: $DST/docs/install.md §2)
cd "$DST/pos" && npm install && npm run build && cd ~/frappe-bench
ls -l "$DST/mypos/public/pos/pos.js" "$DST/mypos/public/order/order.js"

# ⛔ DỪNG — chờ xác nhận Desktop Icon (khối trên) trước khi chạy tiếp

# 6.4 Build asset Frappe
bench build --app mypos

# 6.5 App đã cài trên site? Không thấy "mypos" -> install-app (after_install tạo role + quyền)
bench --site local.com list-apps
#   bench --site local.com install-app mypos

# 6.6 Migrate (DocType, fixtures, workspace, Sidebar, Desktop Icon nếu chế độ lưới icon; after_migrate bổ sung quyền)
bench --site local.com migrate

# 6.7 Xóa cache
bench --site local.com clear-cache
bench --site local.com clear-website-cache

# 6.8 Khởi động lại: Ctrl+C ở terminal đang chạy bench start, rồi
bench start
```

### Selfcheck sau migrate

Chỉ đọc (chạy ngay):

```bash
bench --site local.com execute frappe.desk.doctype.desktop_icon.desktop_icon.is_desktop_icons_page
bench --site local.com execute mypos.selfcheck.desktop_icon_check.check_desktop_icons
bench --site local.com execute mypos.selfcheck.sidebar_check.check_sidebar
bench --site local.com execute mypos.selfcheck.workspace_shortcut_check.check_workspace_shortcuts
bench --site local.com execute mypos.setup.roles.setup_roles_and_permissions        # lần 2+: mọi số 0, lỗi 0
bench --site local.com execute frappe.db.count --args "['Custom Field', {'module': 'MYPOS'}]"   # 35
bench --site local.com scheduler status                                             # disabled -> enable-scheduler
```

Sau khi cấu hình tay (`$DST/docs/install.md` §3) — có ghi dữ liệu thử, đọc docstring từng hàm (`$DST/docs/testing.md`):

```bash
P="<POS Profile>"; I="<mã món VARIANT>"; M="<Mode of Payment tiền mặt>"; L="<Price List của MYPOS Menu>"
for c in walk_in_customer_check.check_walk_in_customer table_card_check.check_table_card \
         draft_cancel_check.check_draft_cancel open_orders_check.check_open_orders \
         shift_owner_check.check_shift_owner payment_status_check.check_payment_status \
         customer_display_check.check_customer_display order_status_check.check_order_status \
         poll_load_check.check_poll_load; do
  bench --site local.com execute mypos.selfcheck.$c --kwargs "{'pos_profile': '$P', 'item_code': '$I', 'mode_of_payment': '$M', 'price_list': '$L'}"
done
bench --site local.com execute mypos.selfcheck.branch_profile_check.check_branch_profile --kwargs "{'pos_profile': '$P'}"
bench --site local.com execute mypos.selfcheck.kitchen_desk_check.check_kitchen_desk
bench --site local.com execute mypos.selfcheck.order_history_selftest.run_order_history_selftest     # gồm order_qr_selftest
# Tham số riêng (docs/testing.md): orders_shift_check, legacy_options_check, surcharge_check
```

### Checklist kiểm tay (PASS / FAIL)

Bảng đầy đủ: `$DST/docs/checklist.md` (`less "$DST/docs/checklist.md"`). Tóm tắt:

| # | Hạng mục | PASS / FAIL |
|---|---|---|
| A1–A4 | Workspace + sidebar theo role (Administrator, Manager, Cashier, Kitchen) | |
| A5 | Mở `/desk` thấy icon MYPOS đúng role (site ở chế độ lưới icon) | |
| A6 | Bấm icon mở đúng workspace / `/pos/kitchen`, sidebar MYPOS đúng | |
| A7 | User không có role POS không thấy icon / workspace MYPOS | |
| B1–B6 | Bán món, tiền mặt, Kitchen, kết thúc đơn, thẻ bàn, hủy đơn | |
| C1–C4 | Chuyển khoản + SePay giả lập (curl) | |
| D1–D5 | Web đặt món QR `/order/<token>` | |
| E1–E4 | Customer Display, `/pos/status` | |
| F1–F3 | Đóng ca | |
| G1–G2 | Scheduler, job tự hủy | |
