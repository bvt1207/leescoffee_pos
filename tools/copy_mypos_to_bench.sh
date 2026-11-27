#!/usr/bin/env bash
# Copy app mypos từ repo PROJECTPOS (ổ Windows, /mnt/c) sang bench (WSL). Hướng dẫn: tools/README_copy_mypos.md
#
#   bash tools/copy_mypos_to_bench.sh              # = --dry-run: chỉ liệt kê, không ghi gì
#   bash tools/copy_mypos_to_bench.sh --diff [f]   # diff -u bản ở DST với bản ở SRC cho file sẽ bị thay (hoặc 1 file f)
#   bash tools/copy_mypos_to_bench.sh --apply      # sao lưu DST rồi copy (hỏi xác nhận)
#   bash tools/copy_mypos_to_bench.sh --verify     # diff -rq SRC DST (phải rỗng)
#   bash tools/copy_mypos_to_bench.sh --next       # chỉ in các lệnh chạy tiếp + checklist
#
# Không dùng --delete (file đã xóa ở SRC vẫn còn ở DST: script chỉ liệt kê). Không đụng DST/.git.

set -euo pipefail

SRC="/mnt/c/Users/ADMIN/OneDrive/Pictures/Năm 4 UIT/ERPNEXT/PROJECTPOS/mypos"
DST="$HOME/frappe-bench/apps/mypos"
SITE="local.com"
BACKUP_DIR="$HOME/mypos_backups"

BENCH_DIR="$(dirname "$(dirname "$DST")")"

# Loại trừ khi copy. Mẫu bắt đầu bằng "/" tính từ gốc SRC.
RSYNC_EXCLUDES=(
	--exclude=".git/"
	--exclude="node_modules/"
	--exclude="__pycache__/"
	--exclude="*.pyc"
	--exclude=".env"
	--exclude=".env.*"
	--exclude="*.egg-info/"
	--exclude="/mypos/public/pos/"
	--exclude="/mypos/public/order/"
	--exclude="/dist/"
	--exclude="/build/"
	--exclude="/pos/dist/"
)
# -r -l -t: KHÔNG -p/-o/-g (file trên /mnt/c hiện quyền 777 / owner Windows); quyền đích chuẩn 755 / 644.
# --checksum: so nội dung (mtime trên /mnt/c không tin được).
RSYNC_OPTS=(-rlt --checksum --chmod=D755,F644 --itemize-changes)
# diff -rq: --exclude so theo TÊN (basename); 2 thư mục build lọc riêng bằng grep.
DIFF_EXCLUDES=(--exclude=.git --exclude=node_modules --exclude=__pycache__ --exclude="*.pyc" --exclude=.env --exclude="*.egg-info")
BUILD_RE='/mypos/public(/(pos|order)(/| |$)|: (pos|order)$)'

# File khung do `bench new-app` sinh ở DST, sẽ bị bản trong SRC thay: in riêng để xem diff trước khi apply.
SKELETON=(pyproject.toml README.md license.txt .gitignore .editorconfig .eslintrc .pre-commit-config.yaml
	mypos/__init__.py mypos/hooks.py mypos/modules.txt mypos/patches.txt)

red() { printf '\033[31m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
hr() { printf '%s\n' "------------------------------------------------------------------------"; }

die() {
	red "LỖI: $*"
	exit 1
}

# ---------------------------------------------------------------- kiểm tra
check_src() {
	[ -d "$SRC" ] || die "SRC không tồn tại: $SRC (OneDrive chưa đồng bộ? sai đường dẫn?)"
	local n
	n=$(find "$SRC" -type f -not -path "*/node_modules/*" -not -path "*/.git/*" | wc -l)
	[ "$n" -gt 0 ] || die "SRC rỗng: $SRC"
	[ -f "$SRC/pyproject.toml" ] && [ -f "$SRC/mypos/hooks.py" ] || die "SRC không phải gốc app mypos (thiếu pyproject.toml / mypos/hooks.py)"
	grep -q '^app_name = "mypos"' "$SRC/mypos/hooks.py" || die "SRC/mypos/hooks.py không có app_name = \"mypos\""
	echo "SRC: $SRC ($n file, không tính node_modules)"
	# File văn bản có CRLF (Windows) -> cảnh báo (Python / bash trên Linux có thể lỗi).
	local crlf
	crlf=$({
		grep -rIl $'\r' "$SRC" --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=pos --exclude-dir=order 2>/dev/null
		grep -rIl $'\r' "$SRC/pos" --exclude-dir=node_modules 2>/dev/null
	} | head -20 || true)
	if [ -n "$crlf" ]; then
		yellow "CẢNH BÁO: file có xuống dòng CRLF trong SRC (nên chuyển về LF trước khi copy):"
		printf '%s\n' "$crlf" | sed 's/^/  /'
	fi
	if grep -rIliE 'lee[s]coffee' "$SRC" --exclude-dir=node_modules --exclude-dir=.git >/dev/null 2>&1; then
		yellow "CẢNH BÁO: SRC còn chuỗi tên app cũ:"
		grep -rIliE 'lee[s]coffee' "$SRC" --exclude-dir=node_modules --exclude-dir=.git | sed 's/^/  /'
	fi
}

# return 0 nếu DST là app mypos; in cảnh báo nếu không
check_dst() {
	local ok=0
	if [ ! -d "$DST" ]; then
		yellow "CẢNH BÁO: DST không tồn tại: $DST (chưa chạy bench get-app / new-app mypos?)"
		return 1
	fi
	[ -f "$DST/mypos/hooks.py" ] && grep -q '^app_name = "mypos"' "$DST/mypos/hooks.py" || {
		yellow "CẢNH BÁO: $DST/mypos/hooks.py không có app_name = \"mypos\" — DST có phải thư mục app mypos?"
		ok=1
	}
	[ -f "$DST/pyproject.toml" ] && grep -q '^name = "mypos"' "$DST/pyproject.toml" || {
		yellow "CẢNH BÁO: $DST/pyproject.toml không có name = \"mypos\""
		ok=1
	}
	[ "$(basename "$(dirname "$DST")")" = "apps" ] || {
		yellow "CẢNH BÁO: DST không nằm trong thư mục apps/ của bench: $DST"
		ok=1
	}
	[ "$DST" != "$SRC" ] || {
		yellow "CẢNH BÁO: DST trùng SRC"
		ok=1
	}
	[ $ok -eq 0 ] && echo "DST: $DST (app mypos, bench $BENCH_DIR)"
	return $ok
}

# ---------------------------------------------------------------- kế hoạch
# Ghi danh sách vào biến toàn cục NEW_FILES / UPDATED_FILES / ONLY_DST
plan() {
	local out
	out=$(rsync -n "${RSYNC_OPTS[@]}" "${RSYNC_EXCLUDES[@]}" "$SRC/" "$DST/")
	NEW_FILES=$(printf '%s\n' "$out" | awk '/^>f\+\+\+\+\+\+\+\+\+ /{ $1=""; sub(/^ /,""); print }')
	UPDATED_FILES=$(printf '%s\n' "$out" | awk '/^>f/ && !/^>f\+\+\+\+\+\+\+\+\+ /{ $1=""; sub(/^ /,""); print }')
	ONLY_DST=$(LC_ALL=C comm -13<(list_files "$SRC") <(list_files "$DST"))
}

list_files() {
	(cd "$1" && find . \( -name .git -o -name node_modules -o -name __pycache__ -o -name "*.egg-info" \
		-o -path ./mypos/public/pos -o -path ./mypos/public/order -o -path ./dist -o -path ./build \) -prune \
		-o -type f ! -name "*.pyc" ! -name ".env" ! -name ".env.*" -print | sed 's#^\./##' | LC_ALL=C sort)
}

count() { [ -z "$1" ] && echo 0 || printf '%s\n' "$1" | wc -l; }

print_plan() {
	hr
	echo "File MỚI (chưa có ở DST): $(count "$NEW_FILES")"
	[ -n "$NEW_FILES" ] && printf '%s\n' "$NEW_FILES" | sed 's/^/  + /'
	hr
	echo "File SẼ BỊ THAY ở DST (nội dung khác): $(count "$UPDATED_FILES")"
	local skel_hit="" f
	for f in "${SKELETON[@]}"; do
		if grep -qxF "$f" <<<"$UPDATED_FILES"; then skel_hit+="$f"$'\n'; fi
	done
	if [ -n "$skel_hit" ]; then
		yellow "  File KHUNG (bench new-app) sẽ bị thay — xem trước: bash $0 --diff <file>"
		printf '%s' "$skel_hit" | sed 's/^/  ! /'
	fi
	[ -n "$UPDATED_FILES" ] && printf '%s\n' "$UPDATED_FILES" | grep -vxF -f <(printf '%s\n' "${SKELETON[@]}") | sed 's/^/  ~ /' || true
	hr
	echo "Chỉ có ở DST (KHÔNG bị xóa — script không dùng --delete; xem tay): $(count "$ONLY_DST")"
	[ -n "$ONLY_DST" ] && printf '%s\n' "$ONLY_DST" | sed 's/^/  ? /'
	hr
	if grep -qx "pyproject.toml" <<<"$UPDATED_FILES"$'\n'"$NEW_FILES"; then
		yellow "pyproject.toml đổi -> sau khi copy chạy: bench setup requirements"
	fi
}

# ---------------------------------------------------------------- các chế độ
do_dry_run() {
	check_src
	check_dst || yellow "(dry-run vẫn liệt kê; --apply sẽ dừng cho tới khi DST đúng)"
	[ -d "$DST" ] || exit 1
	plan
	print_plan
	echo "DRY-RUN: chưa ghi gì. Copy thật: bash $0 --apply"
}

do_diff() {
	check_src >/dev/null
	[ -d "$DST" ] || die "DST không tồn tại: $DST"
	local files
	if [ $# -gt 0 ]; then
		files="$1"
	else
		plan
		files="$UPDATED_FILES"
	fi
	[ -n "$files" ] || {
		echo "Không có file nào sẽ bị thay."
		return 0
	}
	while IFS= read -r f; do
		[ -n "$f" ] || continue
		echo "=== $f   (--- DST hiện tại / +++ SRC sẽ chép sang)"
		diff -u --label "DST/$f" --label "SRC/$f" "$DST/$f" "$SRC/$f" || true
	done <<<"$files"
}

do_verify() {
	check_src >/dev/null
	[ -d "$DST" ] || die "DST không tồn tại: $DST"
	local out
	out=$(diff -rq "${DIFF_EXCLUDES[@]}" "$SRC" "$DST" 2>&1 | grep -Ev "$BUILD_RE" || true)
	if [ -z "$out" ]; then
		green "VERIFY: SRC và DST giống nhau (bỏ qua .git, node_modules, __pycache__, *.pyc, .env, *.egg-info, mypos/public/{pos,order})."
	else
		yellow "VERIFY: còn khác biệt:"
		printf '%s\n' "$out" | sed 's/^/  /'
		echo "  (\"Only in $DST\": file chỉ có ở bench — script không xóa; package-lock.json sinh lại trên Linux cũng sẽ khác)"
		return 1
	fi
}

do_apply() {
	check_src
	check_dst || die "DST không phải thư mục app mypos — dừng, không copy."
	plan
	print_plan
	if [ -z "$NEW_FILES$UPDATED_FILES" ]; then
		green "Không có gì để copy."
		do_verify || true
		print_next
		return 0
	fi
	local need_req=0
	grep -qx "pyproject.toml" <<<"$UPDATED_FILES"$'\n'"$NEW_FILES" && need_req=1
	read -r -p "Copy $(count "$NEW_FILES") file mới + thay $(count "$UPDATED_FILES") file ở DST? Gõ 'yes' để tiếp tục: " ans
	[ "$ans" = "yes" ] || die "Đã hủy."
	mkdir -p "$BACKUP_DIR"
	local bk
	bk="$BACKUP_DIR/mypos-$(date +%Y%m%d-%H%M%S).tar.gz"
	tar -czf "$bk" -C "$(dirname "$DST")" --exclude=node_modules --exclude=__pycache__ \
		--exclude="mypos/mypos/public/pos" --exclude="mypos/mypos/public/order" "$(basename "$DST")"
	green "Đã sao lưu DST: $bk"
	rsync "${RSYNC_OPTS[@]}" "${RSYNC_EXCLUDES[@]}" "$SRC/" "$DST/" | grep -v '^\.d' || true
	green "Đã copy."
	do_verify || true
	NEED_REQ=$need_req print_next
}

print_next() {
	local req_note="(chỉ khi pyproject.toml đổi dependency)"
	[ "${NEED_REQ:-0}" = "1" ] && req_note="(CẦN: pyproject.toml vừa đổi)"
	cat <<EOF

========================================================================
LỆNH CHẠY TIẾP — theo đúng thứ tự, trong WSL
========================================================================
cd "$BENCH_DIR"

# 1. Sao lưu site
bench --site $SITE backup --with-files

# 2. Python requirements $req_note
bench setup requirements

# 3. Build frontend (lỗi thiếu gói nhị phân esbuild / rollup: $SRC/docs/install.md §2)
cd "$DST/pos" && npm install && npm run build && cd "$BENCH_DIR"

# 4. Build asset Frappe của app
bench build --app mypos

# 5. App đã cài trên site chưa? Chưa thấy "mypos" -> install-app (chạy after_install: role + quyền)
bench --site $SITE list-apps
#    bench --site $SITE install-app mypos

# 6. Migrate (DocType, fixtures, workspace, sidebar, desktop icon; after_migrate bổ sung quyền)
bench --site $SITE migrate

# 7. Xóa cache
bench --site $SITE clear-cache
bench --site $SITE clear-website-cache

# 8. Khởi động lại bench: Ctrl+C ở terminal đang chạy bench start, rồi:
bench start

# 9. Scheduler (cron tự hủy Draft quá hạn)
bench --site $SITE scheduler status      # disabled -> bench --site $SITE enable-scheduler

# 10. Script tự kiểm CHỈ ĐỌC (chạy ngay sau migrate)
bench --site $SITE execute mypos.selfcheck.sidebar_check.check_sidebar
bench --site $SITE execute mypos.selfcheck.workspace_shortcut_check.check_workspace_shortcuts
bench --site $SITE execute mypos.setup.roles.setup_roles_and_permissions     # lần 2 trở đi: mọi số = 0, lỗi: 0
bench --site $SITE execute frappe.db.count --args "['Custom Field', {'module': 'MYPOS'}]"   # 35

# 11. Cấu hình tay (site mới): $SRC/docs/install.md §3
#     Company / Price List / Item, Mode of Payment, Branch (thương hiệu + SePay), Customer khách vãng lai,
#     POS Profile (branch, khách vãng lai, payments, income_account), User + Role, Applicable for Users,
#     MYPOS Menu / Option Group / Buzzer / Order QR / Banner, POS Settings, host_name.

# 12. Script tự kiểm có ghi dữ liệu thử (sau bước 11; đọc docstring từng hàm; danh sách: docs/testing.md)
P="<POS Profile>"; I="<mã món VARIANT>"; M="<Mode of Payment tiền mặt>"; L="<Price List của MYPOS Menu>"
for c in walk_in_customer_check.check_walk_in_customer table_card_check.check_table_card \\
         draft_cancel_check.check_draft_cancel open_orders_check.check_open_orders \\
         shift_owner_check.check_shift_owner payment_status_check.check_payment_status \\
         customer_display_check.check_customer_display order_status_check.check_order_status \\
         poll_load_check.check_poll_load; do
  bench --site $SITE execute mypos.selfcheck.\$c --kwargs "{'pos_profile': '\$P', 'item_code': '\$I', 'mode_of_payment': '\$M', 'price_list': '\$L'}"
done
bench --site $SITE execute mypos.selfcheck.branch_profile_check.check_branch_profile --kwargs "{'pos_profile': '\$P'}"
bench --site $SITE execute mypos.selfcheck.kitchen_desk_check.check_kitchen_desk
bench --site $SITE execute mypos.selfcheck.order_history_selftest.run_order_history_selftest   # gồm cả order_qr_selftest
#    Thêm (tham số riêng, xem docs/testing.md): orders_shift_check, legacy_options_check, surcharge_check

# 13. Checklist kiểm tay (in bên dưới, nguồn: docs/checklist.md)
EOF
	if [ -f "$SRC/docs/checklist.md" ]; then
		echo "========================================================================"
		cat "$SRC/docs/checklist.md"
	else
		yellow "Không thấy $SRC/docs/checklist.md"
	fi
}

usage() { sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; }

MODE="${1:---dry-run}"
case "$MODE" in
--dry-run | -n) do_dry_run ;;
--diff) shift; do_diff "$@" ;;
--apply) do_apply ;;
--verify) do_verify ;;
--next) print_next ;;
-h | --help) usage ;;
*)
	usage
	exit 2
	;;
esac
