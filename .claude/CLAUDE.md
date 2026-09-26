# CLAUDE.md — Leescoffee POS (leescoffee_pos)

> File này là bộ não của dự án. Claude Code đọc file này đầu mỗi phiên làm việc để
> hiểu bối cảnh mà không cần giải thích lại. File sẽ mở rộng dần khi dự án tiến triển
> — thêm mục mới thay vì sửa xóa lịch sử quyết định đã chốt.

## 1. Bối cảnh dự án

- Đây là đồ án/khóa luận tốt nghiệp: xây dựng module quản lý bán hàng tại điểm bán
  (POS) cho doanh nghiệp F&B, chạy trên nền ERPNext (Frappe Framework).
- Trường hợp thực tế dùng để thiết kế và demo: **Lee's Coffee** (chuỗi cà phê).
- Đề cương nộp trường dùng tên chung "Xây dựng hệ thống quản lý bán hàng tại điểm bán
  cho doanh nghiệp F&B dựa trên nền tảng ERPNext" — không nêu tên Lee's Coffee, không
  nêu AI trong tên đề tài. Bản thiết kế/demo thực tế vẫn nhắm vào Lee's Coffee và có
  thể mở rộng thêm các phần nâng cao sau khi đề cương được duyệt.
- Đây là dự án cá nhân (không phải sản phẩm thương mại), ưu tiên: đúng nghiệp vụ,
  chạy được thật để demo hội đồng, và có tài liệu rõ ràng để viết báo cáo khóa luận.

## 1b. Nguyên tắc đa dụng (white-label) — RẤT QUAN TRỌNG

Đây là sản phẩm POS dùng chung cho nhiều doanh nghiệp F&B, không phải app riêng cho
Lee's Coffee. **Lee's Coffee chỉ là dữ liệu demo** để trình bày trước hội đồng, sau
này Van sẽ triển khai hệ thống này cho các doanh nghiệp F&B khác nữa.

- **Tuyệt đối không hardcode** tên "Lee's Coffee"/"leescoffee", logo, banner, màu
  thương hiệu hay bất kỳ nội dung đặc thù nào của Lee's Coffee vào code, template,
  hay asset tĩnh (frontend lẫn backend).
- Mọi thông tin thương hiệu (tên quán, logo, banner, màu chủ đạo...) phải là **dữ
  liệu cấu hình** đọc từ DocType (Settings/Branch), không phải giá trị viết chết
  trong code.
- Giao diện thiết kế theo phong cách quán cà phê nói chung (đẹp, chuyên nghiệp, đủ
  tốt để demo) — không thiết kế riêng theo bộ nhận diện của Lee's Coffee.
- Dữ liệu mẫu để test/demo (tên món, giá, logo Lee's Coffee...) nhập qua Desk UI
  hoặc fixtures dữ liệu demo — không nhúng cứng vào source code của app.
- Tên app kỹ thuật hiện tại (`leescoffee_pos`) và App title ("Leescoffee POS") ở
  mục 2 chỉ là tên đặt lúc khởi tạo, không bắt buộc đổi ngay — nhưng nếu về sau cần
  dùng lại cho khách hàng khác, nên cân nhắc đổi sang tên trung tính hơn.

## 2. Nền tảng & công nghệ

| Hạng mục            | Giá trị                                                                      |
| ------------------- | ---------------------------------------------------------------------------- |
| Platform            | ERPNext v16 (Frappe Framework — DocType, workflow, permission, REST API)     |
| Backend             | Python (Frappe Framework)                                                    |
| Frontend POS        | React + TypeScript (TSX) — app riêng, không dùng frontend có sẵn của ERPNext |
| App name (kỹ thuật) | `leescoffee_pos`                                                             |
| App title           | "Leescoffee POS"                                                             |
| Publisher           | BVTHACH                                                                      |
| Version             | 0.0.1 (khởi tạo)                                                             |

**Nguyên tắc kiến trúc quan trọng nhất — không được vi phạm:**
ERPNext là hệ điều hành bên dưới. **Giữ nguyên và tận dụng tối đa các DocType lõi có
sẵn** của ERPNext (Sales Invoice, Customer, Item, POS Profile, Payment Entry, Stock,
Mode of Payment...). Module `leescoffee_pos` **chỉ mở rộng thêm**, không thay thế các
DocType bán hàng/kế toán chuẩn. Lý do: (1) đúng với tên đề tài "dựa trên nền tảng
ERPNext", (2) tận dụng được kế toán/kho có sẵn, (3) khối lượng code ít hơn nhiều so
với viết lại toàn bộ hệ thống bán hàng.

Khi cần dữ liệu mới không có sẵn trong ERPNext (loại đơn, kênh đặt món, trạng thái
pha chế...), cách làm theo thứ tự ưu tiên:

1. Custom DocType **mới hoàn toàn**, đặt đúng `module = Leescoffee Pos` khi tạo, để
   file JSON nằm trong app (đi theo git bình thường) — **không phải Custom DocType
   rời trong DB**.
2. Chỉ dùng Custom Field (gắn lên DocType chuẩn như Sales Invoice) khi thực sự cần
   thêm thuộc tính lên 1 doctype có sẵn. Custom Field kiểu này phải được export qua
   cơ chế **fixtures** trong `hooks.py` để đi theo git — xem mục 6.

## 3. Mô hình nghiệp vụ — giai đoạn hiện tại (2 luồng)

**Không dùng "Table" (quản lý bàn Available/Occupied) như 1 entity có vòng đời.**

Hai field độc lập thay vì gộp chung 1 loại đơn:

- `order_type`: `Take Away` | `Dine In`
- `order_channel`: hiện tại chỉ có `POS` (nhân viên nhập tại quầy). Giá trị `QR Web`
  đã được tính trước trong thiết kế nhưng **chưa xây ở giai đoạn này** — xem mục 3b.

Hai kịch bản vận hành của giai đoạn hiện tại:

| Kịch bản         | order_type | order_channel | Ai đặt món | Thanh toán                             |
| ---------------- | ---------- | ------------- | ---------- | -------------------------------------- |
| Take Away        | Take Away  | POS           | Nhân viên  | Quầy (Cash/QR thanh toán)              |
| Dine In tại quầy | Dine In    | POS           | Nhân viên  | Quầy (Cash/QR thanh toán), có thẻ rung |

**Lưu ý phân biệt quan trọng:** "QR" trong cột Thanh toán ở trên là **QR để thanh
toán** (VietQR qua SePay, khách quét bằng app ngân hàng ngay tại quầy) — khác hoàn
toàn với "kênh QR" (`order_channel = QR Web`) là khách **tự đặt món** qua QR, thứ
đang hoãn sang giai đoạn mở rộng ở mục 3b. Tích hợp SePay để sinh mã thanh toán vẫn
cần làm ở giai đoạn hiện tại.

Quy tắc xuyên suốt (áp dụng cho cả 2 luồng hiện tại):

- **Payment-gated preparation**: đơn chỉ được đẩy sang màn hình pha chế khi đã
  `Paid`. Đơn chưa thanh toán không tồn tại ở khâu pha chế.
- Vòng đời trạng thái đơn: `Draft → Paid → Đang pha chế (Chưa làm / Đã làm) →
Đã hoàn thành`.
- Sau khi bấm "Add Order" trên POS, hệ thống tự động điều hướng sang trang Orders
  và mở sẵn đúng đơn đó để thanh toán ngay — không bắt nhân viên tự tìm lại đơn.
- Trang "Table" cũ được thay bằng **Status board** dùng chung cho cả Take Away và
  Dine In: hiển thị Đang làm / Hoàn thành, kèm gọi số/thẻ rung khi xong.
- Take Away và Dine In tại quầy dùng **thẻ rung vật lý** (hoặc số gọi ảo nếu chưa có
  phần cứng) làm cơ chế gọi khách khi đơn xong.

## 3b. Định hướng mở rộng — Kênh QR (app riêng, làm SAU giai đoạn hiện tại)

Đây là 1 **app Frappe riêng, kết nối với app lõi này**, không gộp chung vào giai
đoạn hiện tại. Ghi lại đây để không quên thiết kế, nhưng **chưa triển khai ngay**.

- **Takeaway QR**: khách tự đặt món mang đi qua QR (không cần ra quầy đặt) → thanh
  toán trên điện thoại → hệ thống tạo đơn thật sau khi thanh toán thành công → khách
  nhận thông báo khi đơn xong → **tự xuống quầy lấy** (giống cơ chế gọi số của
  Take Away hiện tại, chỉ khác là đặt món từ xa).
- **Dine In QR**: QR gắn theo từng bàn, có **đính kèm số bàn** (table number/location
  label) khi quét. Mặc định: khi có thông báo đơn xong, khách **tự biết xuống quầy
  lấy** — giống hệt Takeaway QR.
- **Ngoại lệ khách VIP** (chỉ áp dụng cho Dine In QR): nếu khách/bàn được đánh dấu là
  VIP, hệ thống thông báo cho **nhân viên chủ động mang đồ uống tới tận bàn** thay vì
  để khách tự xuống quầy lấy. Cần: (a) 1 field/flag đánh dấu VIP (trên Customer hoặc
  trên phiên đặt món), (b) logic rẽ nhánh ở bước thông báo hoàn thành — nếu VIP thì
  thông báo nhân viên giao tận bàn, nếu không thì thông báo khách tự xuống lấy.
- Định danh khách qua SĐT (tìm-hoặc-tạo Customer theo SĐT, không OTP ở bản đầu) khi
  dùng bất kỳ kênh QR nào.

## 4. Định hướng phát triển

- Hiện trạng: app Frappe đã scaffold xong (`bench new-app leescoffee_pos`), chưa có
  DocType, API hay logic nghiệp vụ nào.
- Cách tiếp cận: làm từng phần nhỏ nhất một, theo đúng thứ tự phụ thuộc — bắt đầu từ
  DocType cấu hình gốc, rồi tới các luồng nghiệp vụ cụ thể (xem mục 7).
- Frontend React/TSX cho POS sẽ phát triển riêng, gọi REST API của Frappe (hoặc
  nhúng qua Frappe Web Page/Page nếu tiện hơn khi demo) — quyết định chi tiết khi
  bắt đầu phần frontend, chưa chốt cứng ở giai đoạn này.
- Có thể tích hợp thêm dịch vụ ngoài sau này (cổng thanh toán khác, giao hàng, kế
  toán mở rộng) — không thiết kế cứng nhắc chỉ cho SePay.

## 4b. Ràng buộc môi trường làm việc — RẤT QUAN TRỌNG

Claude Code đang chạy trong thư mục `PROJECTPOS`, **bên ngoài** Frappe bench thật
(`frappe-benchver16`). Đây **không phải** một site ERPNext đang chạy.

- **Không tự ý chạy** `bench migrate`, `bench install-app`, hay bất kỳ lệnh nào cần
  một site ERPNext thật đang hoạt động — các lệnh này sẽ lỗi hoặc vô nghĩa khi chạy
  trong `PROJECTPOS`.
- Việc đưa code từ `PROJECTPOS` vào chạy thật diễn ra **thủ công, ngoài phạm vi của
  Claude Code**: Van tự đẩy code lên GitHub, rồi tự tay đưa code đó vào
  `frappe-benchver16/apps/leescoffee_pos` và chạy các lệnh bench cần thiết trên máy
  có bench thật.
- **Sau mỗi task, Claude Code phải luôn để lại 1 mục "Lệnh cần chạy thủ công"** liệt
  kê chính xác các lệnh Van cần chạy trên bench thật để áp dụng thay đổi (ví dụ:
  "chạy `bench migrate` để tạo bảng cho DocType mới `Leescoffee POS Settings`").
  Ghi mục này vào cả trong phản hồi và vào `memory.md`.
- Claude Code có thể và nên: viết code, tạo DocType JSON đúng chuẩn Frappe, viết
  Python logic, kiểm tra cú pháp/cấu trúc file — nhưng không giả định là code đã
  chạy thật hay đã test được trên site cho tới khi Van xác nhận ngược lại.
- **Git**: Claude Code **tự `git commit`** sau mỗi task hoàn thành (message rõ ràng,
  mô tả đúng đã làm gì) để có lịch sử commit sạch, dễ rollback. **Không tự `git
push`** — Van sẽ tự xem lại diff rồi mới đẩy lên GitHub, tránh trường hợp push
  nhầm secret/API key hoặc code còn lỗi lên remote công khai.

## 4c. Quy trình đồng bộ code (PROJECTPOS → bench thật)

`PROJECTPOS` và `frappe-benchver16/apps/leescoffee_pos` là **2 thư mục tách biệt**,
không chung git repo — đồng bộ bằng **copy thủ công**, không phải `git pull`. Quy
trình mỗi lần muốn đưa thay đổi vào chạy thật:

1. Claude Code hoàn thành task trong `PROJECTPOS`, tự `git commit` tại đó.
2. Van xem lại diff, tự `git push` lên GitHub.
3. Van tự tay copy các file đã đổi từ `PROJECTPOS/leescoffee_pos` sang
   `frappe-benchver16/apps/leescoffee_pos` (ghi đè đúng file, đúng đường dẫn tương
   ứng).
4. Van tự chạy các lệnh bench cần thiết (theo mục "Lệnh cần chạy thủ công" mà Claude
   Code để lại) trên bench thật, ví dụ `bench --site [site] migrate`.

**Vì là copy tay, không phải git pull, Claude Code cần đặc biệt cẩn thận:**

- Sau mỗi task, liệt kê rõ **danh sách file đã tạo/sửa** (đường dẫn đầy đủ), không
  chỉ nói chung chung "đã thêm DocType" — để Van biết chính xác cần copy file nào,
  tránh copy thiếu hoặc copy nhầm file cũ.
- Không tự động xóa hoặc đổi tên file đã có nếu không thực sự cần thiết, vì Van
  không đồng bộ bằng git nên khó phát hiện file bị xóa/đổi tên nếu không được nhắc.

## 5. Quy ước code

- Tên DocType, field: tiếng Anh, snake_case cho fieldname (`order_type`,
  `order_channel`), Title Case cho DocType name (`Leescoffee Order Session`).
- Mọi DocType mới của app phải chọn đúng `Module = Leescoffee Pos`.
- Business logic đặt trong `leescoffee_pos/leescoffee_pos/doctype/<doctype>/...py`
  theo đúng convention chuẩn của Frappe (không viết logic rải rác ngoài doctype).
- Document Events (before_insert, validate, on_submit...) khai báo tập trung trong
  `hooks.py`, trỏ tới file logic riêng — theo đúng pattern Frappe chuẩn, dễ maintain
  và dễ review trong báo cáo khóa luận.
- **Không hardcode** tên quán, logo path, banner, hay bất kỳ chuỗi/asset đặc thù nào
  của Lee's Coffee trong component React hay trong Python — luôn đọc từ DocType
  Settings/Branch (xem mục 1b).
- **Checklist bắt buộc cho mọi file DocType JSON** (lỗi đã gặp thực tế, dễ tái diễn):
  - Phải có `"doctype": "DocType"` ở gốc file — đây là metadata bắt buộc, khác với
    field nghiệp vụ tên "doctype" bên trong `fields[]`. Thiếu dòng này gây lỗi
    `KeyError: 'doctype'` khi chạy `bench migrate`.
  - Giá trị `fieldtype` phải đúng casing chuẩn Frappe (Title Case): `Section Break`,
    `Link`, `Data`, `Check`, `Select`, `Password`, `Attach Image`, `Small Text`...
    — không viết thường (`section break` sẽ không được nhận diện đúng).
  - Trước khi báo "xong", tự rà lại toàn bộ file JSON vừa tạo theo đúng 2 điểm trên.

## 6. Triển khai & fixtures

- Custom Field gắn lên DocType chuẩn của ERPNext (nếu có) phải khai báo trong
  `fixtures` của `hooks.py` và chạy `bench export-fixtures` để sinh file JSON commit
  vào git — nếu không, site khác sẽ thiếu field khi cài lại app.
- Không commit `site_config.json`, API key SePay, hay bất kỳ secret nào — dùng
  `bench set-config` hoặc biến môi trường trên từng site.
- Đây là bước Van tự làm (không phải Claude Code): trước khi coi 1 phần là "xong",
  Van tự cài lại trên bench thật (`bench get-app` hoặc copy file theo mục 4c +
  `install-app` + `migrate` trên 1 site sạch nếu nghi ngờ) để chắc chắn không phụ
  thuộc ngầm vào dữ liệu chỉ có sẵn trên máy dev. Claude Code không tự làm được bước
  này — chỉ cần viết code đúng chuẩn và để lại danh sách lệnh cần chạy như mục 4b.

## 7. Lộ trình — Giai đoạn hiện tại (Take Away quầy + Dine In quầy/thẻ rung)

- [ ] DocType cấu hình gốc: `Leescoffee POS Settings` (Single DocType) — chi nhánh
      mặc định, cấu hình SePay (cho QR thanh toán tại quầy), thông tin thương hiệu
      dạng cấu hình (tên quán, logo, banner) — không hardcode, xem mục 1b
- [ ] Branch — thông tin từng chi nhánh, cấu hình SePay riêng theo chi nhánh nếu cần
- [ ] DocType thẻ rung/số gọi (buzzer) cho Dine In tại quầy — trạng thái Sẵn sàng /
      Đang dùng
- [ ] Tích hợp thanh toán SePay tại quầy — sinh VietQR động cho đơn Take Away/Dine
      In, xác nhận qua webhook (đây là QR thanh toán, không phải kênh QR đặt món)
- [ ] Status board: Đang làm / Hoàn thành cho cả Take Away và Dine In, gọi số/thẻ
      rung khi xong
- [ ] Màn hình pha chế (barista screen)
- [ ] Frontend React/TSX cho POS: chọn món, chọn loại đơn, thanh toán — giao diện
      phong cách quán cà phê tổng quát, không hardcode branding Lee's Coffee
- [ ] Chuẩn bị demo hội đồng, nhập dữ liệu Lee's Coffee qua Desk UI làm dữ liệu demo

## 7b. Lộ trình — Giai đoạn mở rộng (app riêng, làm SAU, xem mục 3b)

- [ ] App Frappe riêng cho kênh QR, kết nối với app lõi qua API/DocType dùng chung
- [ ] Takeaway QR: đặt món mang đi qua QR → thanh toán → thông báo → khách tự xuống
      quầy lấy
- [ ] Dine In QR: QR gắn số bàn → mặc định thông báo khách tự xuống quầy lấy
- [ ] Cơ chế khách VIP cho Dine In QR: đánh dấu VIP → nhân viên chủ động giao tận
      bàn thay vì khách tự lấy
- [ ] Định danh khách qua SĐT (tìm-hoặc-tạo Customer) cho các kênh QR

## 8. Việc KHÔNG làm ở bản đầu (out of scope)

- Không xây dựng lại Sales Invoice/kế toán từ đầu.
- Không làm app di động riêng cho khách hàng (dùng web mobile-friendly là đủ).
- Không làm tách bill nhóm nhiều người trong 1 phiên QR (pre-pay đơn giản trước).
- Không làm kênh QR (Takeaway QR, Dine In QR) ở giai đoạn này — xem mục 3b/7b, đây
  là app mở rộng làm sau, không phải việc của giai đoạn hiện tại.
- Không tự nghiên cứu thuật toán AI mới — nếu có tầng giám sát/dự đoán vận hành,
  chỉ tích hợp phương pháp có sẵn phù hợp với bài toán thực tế.
