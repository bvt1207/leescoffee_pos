# Session Management — Leescoffee POS

> Tự động tải bởi Claude Code mỗi phiên làm việc. Tham chiếu từ CLAUDE.md mục 10.

## Nguyên tắc

- **Mỗi task là 1 phiên**: Claude Code hoàn thành task → commit code → báo cáo. Van duyệt → Claude Code cập nhật tài liệu → kết thúc phiên.
- **Mỗi phiên cách nhau** bởi quá trình review, push, copy code sang bench thật, chạy lệnh thủ công của Van.
- **Git log là nguồn của sự thật**: "Đã làm gì" được theo dõi qua `git log`, không ghi trùng vào CLAUDE.md.
- **CLAUDE.md chứa**: bối cảnh dự án, nguyên tắc, lộ trình, quy tắc. Không chứa thông tin chỉ liên quan một phiên.
- **Kiểm tra token**: Khi sử dụng vượt ~60% auto-compact window, nhắc Van mở phiên mới để tránh mất context.

## Khi phải ngắt giữa task

Nếu buộc phải dừng giữa task (timeout/token hết):

1. **Ghi handoff**: Tạo `.claude/docs/handoff.md` (tối đa 15 dòng) ghi rõ:
   - Đang làm gì (task hiện tại)
   - Đã xong phần nào (file/commit đã hoàn thành)
   - Quyết định đang chờ (nếu có)
   - Việc kế tiếp cần làm
   - Lệnh Van cần chạy thủ công

2. **Đầu phiên mới**: Đọc `handoff.md`, tóm tắt lại cho Van, xóa nội dung file.

## Khi Van hỏi

Tóm tắt trong 3-4 câu:
- Giai đoạn hiện tại (task đang làm)
- Ran đỏi bench/git (code đã commit, đang chờ Van test migate)
- Việc kế tiếp

## Tác phẩm khi Van duyệt

Sau khi Van nói "duyệt"/"ok":
1. Cập nhật CLAUDE.md: tick checklist mục 7, cập nhật mục 10 nếu có thay đổi cấu trúc
2. Commit riêng với message bắt đầu bằng `docs:`
3. Báo cho Van mở phiên mới nếu đây là task cuối cùng hoặc token đang cao