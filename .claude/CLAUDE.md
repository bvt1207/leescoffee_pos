# CLAUDE.md — Leescoffee POS (leescoffee_pos)

> File này là bộ não của dự án. Claude Code đọc file này đầu mỗi phiên làm việc để
> hiểu bối cảnh mà không cần giải thích lại. Xem mục 9 để biết quy tắc tự bảo trì
> file này: từ nay Claude Code tự cập nhật, Van không chỉnh tay.

## 1. Bối cảnh dự án

- Đây là đồ án/khóa luận tốt nghiệp: xây dựng module quản lý bán hàng tại điểm bán
  (POS) cho doanh nghiệp F&B, chạy trên nền ERPNext (Frappe Framework).
- Trường hợp thực tế dùng để thiết kế và demo: **Lee's Coffee** (chuỗi cà phê).
- Đề cương nộp trường dùng tên chung "Xây dựng hệ thống quản lý bán hàng tại điểm bán
  cho doanh nghiệp F&B dựa trên nền tảng ERPNext" — không nêu tên Lee's Coffee, không
  nêu AI trong tên đề tài. Bản thiết kế/demo thực tế vẫn nhắm vào Lee's Coffee và có
  thể mở rộng thêm các phần nâng cao sau khi đề cương được duyệt.
- Dự án cá nhân, ưu tiên: đúng nghiệp vụ, chạy được thật để demo hội đồng, có tài
  liệu rõ ràng để viết báo cáo khóa luận.

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
- Tên app kỹ thuật hiện tại (`leescoffee_pos`) và App title ("Leescoffee POS") chỉ
  là tên đặt lúc khởi tạo, không bắt buộc đổi ngay — nhưng nếu về sau cần dùng lại
  cho khách hàng khác, nên cân nhắc đổi sang tên trung tính hơn.

## 2. Nền tảng, công nghệ & nguyên tắc kiến trúc

| Hạng mục            | Giá trị                                                                      |
| ------------------- | ---------------------------------------------------------------------------- |
| Platform            | ERPNext v16 (Frappe Framework — DocType, workflow, permission, REST API)     |
| Backend             | Python (Frappe Framework)                                                    |
| Frontend POS        | React + TypeScript (TSX) — app riêng, không dùng frontend có sẵn của ERPNext |
| App name (kỹ thuật) | `leescoffee_pos`                                                             |
| App title           | "Leescoffee POS"                                                             |
| Publisher           | BVTHACH                                                                      |

**Nguyên tắc kiến trúc quan trọng nhất — không được vi phạm:**
ERPNext là hệ điều hành bên dưới. **Giữ nguyên và tận dụng tối đa các DocType lõi có
sẵn**, đặc biệt là **`POS Invoice`** — đây là doctype giao dịch chính mà quầy bán
hàng thực tế tạo ra (đã có 164 bản ghi thật đang chạy trên bench), **không phải**
`Sales Invoice`. Các doctype lõi khác cần giữ nguyên: `Customer`, `Item`,
`POS Profile`, `POS Opening Entry`, `POS Closing Entry`, `Payment Entry`, `Stock`,
`Mode of Payment`. Module `leescoffee_pos` **chỉ mở rộng thêm**, không thay thế các
DocType bán hàng/kế toán chuẩn. Lý do: (1) đúng với tên đề tài "dựa trên nền tảng
ERPNext", (2) tận dụng được kế toán/kho có sẵn, (3) khối lượng code ít hơn nhiều so
với viết lại toàn bộ hệ thống bán hàng.

**Ghi chú quan trọng về vòng đời:** `POS Invoice` đã có sẵn field `status` chuẩn của
ERPNext (Draft → Paid → Consolidated, hoặc Return/Cancelled...) — dùng cho mục đích
thanh toán/kế toán, **giữ nguyên, không đụng vào**. Vòng đời pha chế
(`Đang pha chế: Chưa làm → Đã làm → Đã hoàn thành`, xem mục 3) phải nằm ở **1 Custom
Field riêng** (`custom_kitchen_status`) trên `POS Invoice`, không dùng chung field
`status` gốc, tránh xung đột với logic có sẵn của ERPNext. Validate chỉ cho set
`custom_kitchen_status` khi `status == "Paid"` (chính xác hơn `docstatus == 1`, vì
`docstatus == 1` cũng bao gồm cả Consolidated/Return). `POS Invoice` sau khi đóng ca
được ERPNext tự gộp vào `Sales Invoice` qua `POS Invoice Merge Log` — cơ chế có sẵn,
không cần động vào.

Khi cần dữ liệu mới không có sẵn trong ERPNext (loại đơn, kênh đặt món, trạng thái
pha chế, thẻ rung...), thứ tự ưu tiên:

1. Custom DocType **mới hoàn toàn**, đặt đúng `module = Leescoffee Pos` khi tạo, để
   file JSON nằm trong app (đi theo git bình thường) — **không phải Custom DocType
   rời trong DB**.
2. Chỉ dùng Custom Field (gắn lên DocType chuẩn như **`POS Invoice`**) khi thực sự
   cần thêm thuộc tính — ví dụ `order_type`, `order_channel`, `custom_kitchen_status`,
   Link tới thẻ rung. Phải export qua **fixtures** trong `hooks.py` để đi theo git —
   xem mục 6.

## 3. Mô hình nghiệp vụ — giai đoạn hiện tại (2 luồng)

**Không dùng "Table" (quản lý bàn Available/Occupied) như 1 entity có vòng đời.**

Hai field độc lập — cả hai là **Custom Field trên `POS Invoice`**:

- `order_type`: `Take Away` | `Dine In`
- `order_channel`: hiện tại chỉ có `POS` (nhân viên nhập tại quầy). Giá trị `QR Web`
  đã tính trước trong thiết kế nhưng **chưa xây ở giai đoạn này** — xem mục 3b.

Hai kịch bản vận hành của giai đoạn hiện tại:

| Kịch bản         | order_type | order_channel | Ai đặt món | Thanh toán                | Gọi khách khi xong           |
| ---------------- | ---------- | ------------- | ---------- | ------------------------- | ---------------------------- |
| Take Away        | Take Away  | POS           | Nhân viên  | Quầy (Cash/QR thanh toán) | Gọi tên/số trên Status board |
| Dine In tại quầy | Dine In    | POS           | Nhân viên  | Quầy (Cash/QR thanh toán) | Thẻ rung vật lý              |

**Lưu ý phân biệt quan trọng:** "QR" trong cột Thanh toán là **QR để thanh toán**
(VietQR qua SePay, khách quét bằng app ngân hàng ngay tại quầy) — khác hoàn toàn với
"kênh QR" (`order_channel = QR Web`) là khách **tự đặt món** qua QR, đang hoãn sang
mục 3b. Tích hợp SePay để sinh mã thanh toán vẫn cần làm ở giai đoạn hiện tại.

**Dine In tại quầy** dùng **thẻ rung vật lý** vì khách ở lại trong quán chờ.
**Take Away không dùng thẻ rung** — gọi tên/số thứ tự trên Status board, vì khách
take away có thể rời khỏi khu vực chờ. Field Link `buzzer` trên `POS Invoice`
**chỉ áp dụng khi `order_type = Dine In`**. Buzzer là tài nguyên dùng lại theo pool
(`Sẵn sàng ⇄ Đang dùng`), không có vòng đời "Occupied" cố định như bàn.

Quy tắc xuyên suốt (áp dụng cho cả 2 luồng hiện tại):

- **Payment-gated preparation**: `custom_kitchen_status` chỉ được set khi
  `POS Invoice.status == "Paid"`. Đơn chưa thanh toán không tồn tại ở khâu pha chế.
- Vòng đời `custom_kitchen_status`: (trống) → `Chưa làm` (ngay khi Paid) →
  `Đã làm` (barista bắt đầu) → `Đã hoàn thành` (barista xong) — độc lập hoàn toàn
  với field `status` gốc của POS Invoice.
- Sau khi bấm "Add Order" trên POS, hệ thống tự động điều hướng sang trang Orders
  và mở sẵn đúng đơn đó để thanh toán ngay — không bắt nhân viên tự tìm lại đơn.
- Trang "Table" cũ được thay bằng **Status board** dùng chung cho cả Take Away và
  Dine In: hiển thị Đang làm / Hoàn thành, kèm gọi tên/số (Take Away) hoặc thẻ rung
  (Dine In) khi xong.
- Reset buzzer về `Sẵn sàng` xảy ra khi nhân viên xác nhận khách đã nhận món tại
  quầy (hành động riêng, sau khi `custom_kitchen_status` đã là `Đã hoàn thành`) —
  không tự động reset ngay khi barista đánh dấu xong, vì khách có thể chưa tới lấy.
- Hủy đơn hoặc hủy gán thẻ trước khi xong: buzzer đang `Đang dùng` reset về
  `Sẵn sàng` ngay nếu đơn chưa `Đã làm`.

## 3b. Định hướng mở rộng — Kênh QR (app riêng, làm SAU giai đoạn hiện tại)

Đây là 1 **app Frappe riêng, kết nối với app lõi này**, không gộp chung vào giai
đoạn hiện tại. Ghi lại đây để không quên thiết kế, nhưng **chưa triển khai ngay**.

- **Takeaway QR**: khách tự đặt món mang đi qua QR → thanh toán trên điện thoại →
  hệ thống tạo đơn thật sau khi thanh toán thành công → khách nhận thông báo khi
  đơn xong → **tự xuống quầy lấy** (giống cơ chế gọi số của Take Away hiện tại).
- **Dine In QR**: QR gắn theo từng bàn, có **đính kèm số bàn** khi quét. Mặc định:
  khi có thông báo đơn xong, khách **tự biết xuống quầy lấy** — giống Takeaway QR.
- **Ngoại lệ khách VIP** (chỉ Dine In QR): nếu khách/bàn được đánh dấu VIP, hệ thống
  báo cho **nhân viên chủ động mang đồ uống tới tận bàn** thay vì khách tự xuống
  lấy. Cần: (a) field/flag đánh dấu VIP (Customer hoặc phiên đặt món), (b) logic rẽ
  nhánh ở bước thông báo hoàn thành.
- Định danh khách qua SĐT (tìm-hoặc-tạo Customer theo SĐT, không OTP ở bản đầu) cho
  bất kỳ kênh QR nào.

## 4. Định hướng phát triển & môi trường làm việc

- Hiện trạng: app Frappe đã scaffold, đã có DocType đầu tiên (`Leescoffee POS
Settings`), đang làm `Leescoffee Buzzer` + Custom Field trên POS Invoice.
- Cách tiếp cận: làm từng phần nhỏ nhất một, theo đúng thứ tự phụ thuộc (mục 7).
- Frontend React/TSX cho POS phát triển riêng, gọi REST API của Frappe (hoặc nhúng
  qua Frappe Web Page nếu tiện hơn khi demo) — chưa chốt cứng, quyết định khi bắt
  đầu phần frontend.

**Ràng buộc môi trường làm việc — RẤT QUAN TRỌNG:** Claude Code chạy trong thư mục
`PROJECTPOS`, **bên ngoài** Frappe bench thật (`frappe-benchver16`). Đây không phải
site ERPNext đang chạy.

- **Không tự ý chạy** `bench migrate`, `bench install-app`, hay bất kỳ lệnh cần site
  thật đang hoạt động.
- Đưa code vào chạy thật diễn ra **thủ công, ngoài phạm vi Claude Code**: Van tự
  review commit, tự đẩy lên GitHub, tự copy vào `frappe-benchver16/apps/leescoffee_pos`,
  tự chạy lệnh bench trên bench thật.
- **Sau mỗi task, luôn để lại mục "Lệnh cần chạy thủ công"** liệt kê chính xác lệnh
  Van cần chạy trên bench thật.
- **Git**: Claude Code **tự `git commit`** sau mỗi task hoàn thành (message rõ
  ràng). **Không tự `git push`** — Van tự xem diff rồi mới đẩy lên GitHub.

**Quy trình đồng bộ code (PROJECTPOS → bench thật):** `PROJECTPOS` và
`frappe-benchver16/apps/leescoffee_pos` là **2 thư mục tách biệt**, không chung git
repo — đồng bộ bằng **copy thủ công**, không phải `git pull`.

1. Claude Code hoàn thành task, tự `git commit` tại `PROJECTPOS`.
2. Van xem diff, tự `git push` lên GitHub.
3. Van tự copy các file đã đổi sang `frappe-benchver16/apps/leescoffee_pos`.
4. Van tự chạy lệnh bench cần thiết trên bench thật.

Vì là copy tay, Claude Code cần: (a) sau mỗi task, liệt kê rõ **danh sách file đã
tạo/sửa** (đường dẫn đầy đủ) — không nói chung chung; (b) không tự xóa/đổi tên file
đã có nếu không cần thiết, vì Van không đồng bộ bằng git nên khó phát hiện.

## 5. Quy ước code

- Tên DocType, field: tiếng Anh, snake_case cho fieldname (`order_type`,
  `order_channel`), Title Case cho DocType name (`Leescoffee Buzzer`).
- Mọi DocType mới của app phải chọn đúng `Module = Leescoffee Pos`.
- Business logic đặt trong `leescoffee_pos/leescoffee_pos/doctype/<doctype>/...py`
  theo đúng convention chuẩn của Frappe.
- Document Events (before_insert, validate, on_submit...) khai báo tập trung trong
  `hooks.py`, trỏ tới file logic riêng.
- **Không hardcode** tên quán, logo path, banner, hay bất kỳ chuỗi/asset đặc thù nào
  của Lee's Coffee trong component React hay Python — luôn đọc từ DocType
  Settings/Branch (mục 1b).
- **Checklist bắt buộc cho mọi file DocType JSON** (lỗi thực tế đã gặp, dễ tái diễn):
  - Phải có `"doctype": "DocType"` ở gốc file — thiếu dòng này gây lỗi
    `KeyError: 'doctype'` khi chạy `bench migrate`.
  - Giá trị `fieldtype` phải đúng casing chuẩn Frappe (Title Case): `Section Break`,
    `Link`, `Data`, `Check`, `Select`, `Password`, `Attach Image`, `Small Text`...
  - Trước khi báo "xong", tự rà lại toàn bộ file JSON vừa tạo theo đúng 2 điểm trên.
- **Đường dẫn import module**: mọi đường dẫn import trỏ vào code bên trong thư mục module (doctype/, hoặc các thư mục con khác cùng cấp) bắt buộc viết đủ
  `leescoffee_pos.leescoffee_pos.<đường dẫn>`, không viết tắt 1 cấp `leescoffee_pos.<đường dẫn>`.
  (Ví dụ: `leescoffee_pos.leescoffee_pos.doctype.pos_invoice_hooks.pos_invoice_hooks.PosInvoiceHooks.on_submit`).

- **Native lifecycle method vs doc_events** (checklist mới):
  - Native Document lifecycle method (validate, before_save, on_update, on_submit...) 
    viết trực tiếp trong class kế thừa Document → Frappe tự gọi. **KHÔNG đăng ký lại trong hooks.py -> doc_events**.
  - Custom cross-cutting logic cần hook từ app (như POS Invoice) → dùng doc_events.
  - Frappe v16 resolve doc_events theo "module.attribute" — KHÔNG reference trực tiếp "module.ClassName.method". 
    Giữ class để tổ chức logic, nhưng expose thêm module-level wrapper function cùng tên sự kiện, mỗi hàm chỉ
    gọi lại method tương ứng trên class. hooks.py chỉ reference tới wrapper này.
  - DocType thuần cấu hình (như Leescoffee POS Settings), không có custom lifecycle logic → không thêm doc_events chỉ để cho có.

## 6. Triển khai & fixtures

- Custom Field gắn lên DocType chuẩn của ERPNext phải khai báo trong `fixtures` của
  `hooks.py` và chạy `bench export-fixtures` để sinh file JSON commit vào git.
  Custom DocType mới hoàn toàn thì **không cần** fixtures.
- Không commit `site_config.json`, API key SePay, hay bất kỳ secret nào — dùng
  `bench set-config` hoặc biến môi trường trên từng site.
- Trước khi coi 1 phần là "xong": đây là bước Van tự làm trên bench thật (cài lại
  trên site sạch nếu nghi ngờ phụ thuộc ngầm) — Claude Code không tự làm được bước
  này, chỉ cần viết code đúng chuẩn và để lại danh sách lệnh cần chạy và test case
  (mục 9).

## 7. Lộ trình — Giai đoạn hiện tại (Take Away quầy + Dine In quầy/thẻ rung)

Quy ước: chỉ tick `[x]` sau khi Van duyệt task (mục 9).

- [x] DocType cấu hình gốc `Leescoffee POS Settings` (Single DocType) — chi nhánh
      mặc định, thông tin thương hiệu dạng cấu hình. **Đã test Pass**.
- [x] `Leescoffee Buzzer` (Custom DocType) + Custom Field trên `POS Invoice`
      (`order_type`, `order_channel`, `custom_kitchen_status`, `buzzer`). **Đã test Pass**.
- [x] Branch — thông tin từng chi nhánh, cấu hình SePay riêng theo chi nhánh nếu cần
      (không còn fallback Settings). **Đã test Pass**
- [x] Tích hợp thanh toán SePay tại quầy — sinh VietQR động, xác nhận qua webhook, dùng native ERPNext POS Invoice.payments flow (xóa create_payment_entry())
      **Đã test Pass** (TC1-TC5, duplicate webhook trả về `{success: true, already_processed: true}`)
- [ ] Status board: Đang làm / Hoàn thành cho cả Take Away và Dine In, gọi tên/số
      hoặc thẻ rung khi xong
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

- Không xây dựng lại POS Invoice/Sales Invoice/kế toán từ đầu.
- Không làm app di động riêng cho khách hàng (dùng web mobile-friendly là đủ).
- Không làm tách bill nhóm nhiều người trong 1 phiên QR (pre-pay đơn giản trước).
- Không làm kênh QR (Takeaway QR, Dine In QR) ở giai đoạn này — xem mục 3b/7b.
- Không tự nghiên cứu thuật toán AI mới — nếu có tầng giám sát/dự đoán vận hành,
  chỉ tích hợp phương pháp có sẵn phù hợp với bài toán thực tế.

## 9. Tự bảo trì tài liệu & quy trình mỗi task

Claude Code tự bảo trì file này. Van không chỉnh tay. Mỗi task đi theo đúng nhịp:

1. **Code xong** → tự `git commit` code, rồi báo cáo gồm: danh sách file đã tạo/sửa,
   lệnh Van cần chạy thủ công, và mục **Test case** (quy ước bên dưới).
2. **Van tự test** trên bench thật rồi phản hồi.
3. **Van duyệt** (nói "duyệt", "ok" hoặc tương đương) → Claude Code mới cập nhật
   CLAUDE.md: mục 10 (cấu trúc thư mục), tick checklist mục 7, ghi quyết định mới nếu
   có. Commit riêng, message bắt đầu bằng `docs:`.
4. **Van báo lỗi** → sửa code, báo cáo lại; không đụng CLAUDE.md cho tới khi duyệt.

Quy ước mục **Test case** trong mỗi báo cáo:

- Tối đa 5 test case, mỗi test 1 dòng theo mẫu:
  `[TC1] Thao tác trên Desk UI hoặc bench console -> Kết quả mong đợi`.
- Gồm: 1–2 test đường chính, 1 test trường hợp lỗi (nhập thiếu field bắt buộc, gán
  thẻ rung đang bận...), 1 test dữ liệu đã lưu còn nguyên sau khi reload.
- Chỉ viết test Van tự chạy được trên bench thật; không viết test giả định Claude
  Code tự chạy được.
- Cuối phần test ghi sẵn dòng: `Kết quả: Pass / Fail (Van điền)`.

Các quy tắc bảo trì khác:

- Khi cấu trúc thư mục code thay đổi (thêm DocType, file mới, tổ chức lại), cập nhật
  mục 10 cho khớp thực tế — nhưng chỉ sau khi Van duyệt task (bước 3).
- Khi CLAUDE.md vượt khoảng 300–400 dòng, hoặc 1 mục quá dài/chi tiết, tự đề xuất
  tách mục đó ra file riêng trong `rules/` (`workflow.md`, `design.md`,
  `tech-defaults.md`...), chỉ giữ 1–2 dòng tham chiếu trong CLAUDE.md — không xóa
  nội dung, chỉ di chuyển.
- Khi phát hiện 1 thao tác lặp lại nhiều lần theo đúng quy trình cố định (ví dụ mỗi
  lần tạo DocType mới đều theo N bước giống nhau), chủ động đề xuất viết thành
  `skills/<tên-việc>.md` thay vì lặp lại hướng dẫn mỗi lần.
- Mỗi lần tự sửa CLAUDE.md hoặc tách file mới, báo rõ đã sửa mục nào, tách ra file
  nào, để Van không phải đọc lại toàn bộ file.

## 10. Cấu trúc thư mục

> Bản khởi tạo này dựng từ ảnh chụp thư mục, chưa đối chiếu với đĩa. Ở lần cập nhật
> đầu tiên, Claude Code phải kiểm tra lại với thư mục thực tế và sửa cho đúng.
> Sau đó chỉ cập nhật sau khi Van duyệt task (mục 9, bước 3).

```text
PROJECTPOS/
├── .claude/
│   ├── CLAUDE.md                  # file này — bộ não dự án
│   ├── CLAUDE.local.md            # ghi chú riêng, không đẩy lên GitHub
│   ├── memory.md                  # bộ nhớ làm việc của Claude Code (index)
│   ├── memory/
│   │   └── memory_note_branding_fallback.md  # note: Branch có field thương hiệu, ưu tiên Branch, fallback Settings
│   ├── settings.json              # permissions + hooks
│   ├── settings.local.json        # settings riêng, không đẩy lên GitHub
│   ├── agents/                    # chưa dùng
│   ├── rules/                     # chưa dùng (tách từ CLAUDE.md khi quá dài)
│   └── skills/                    # chưa dùng (viết khi có quy trình lặp lại)
└── leescoffee_pos/                # thư mục app Frappe (git repo)
    ├── pyproject.toml, README.md, license.txt
    ├── .gitignore, .editorconfig, .eslintrc, .pre-commit-config.yaml
    └── leescoffee_pos/            # package Python của app
        ├── __init__.py
        ├── hooks.py               # hooks, document events, fixtures
        ├── modules.txt            # danh sách module ("Leescoffee Pos")
        ├── patches.txt
        ├── config/
        ├── patches/
        ├── public/
        ├── templates/
        ├── www/
        └── leescoffee_pos/        # module "Leescoffee Pos"
            └── doctype/
                ├── leescoffee_pos_settings/   # Single DocType — cấu hình gốc (Đã duyệt)
                │   ├── __init__.py
                │   ├── leescoffee_pos_settings.json
                │   └── leescoffee_pos_settings.py
                ├── leescoffee_buzzer/       # DocType mới: thẻ rung (Đã duyệt)
                │   ├── __init__.py
                │   ├── leescoffee_buzzer.json
                │   └── leescoffee_buzzer.py
                ├── pos_invoice_hooks/       # Hooks cho POS Invoice (Đã duyệt)
                │   ├── __init__.py
                │   └── pos_invoice_hooks.py
                └── branch_config/           # Mới: config Branch và helper
                    ├── __init__.py
                    └── branch_config.py
```

## 9. Ghi chú logic webhook SePay (dạng code snapshot)

**Hàm:** `leescoffee_pos/leescoffee_pos/doctype/sepay/sepay.py::sepay_webhook()`

**Luồng xử lý:**

1. **Parse payload JSON** từ SePay (fields: `transferAmount`, `id`/`referenceCode`, `transferType`, `content`/`code`)
2. **Normalize mã** (bỏ dấu `-`, khoảng trắng, chữ hoa) để so khớp `payment_code` với `content`
3. **Tìm POS Invoice Draft** (docstatus=0) có `payment_code` khớp `content`
4. **Idempotent:** Nếu `payment_status == "Đã thanh toán"` → trả về `{success: true, already_processed: true}`
5. **Validate:** invoice ở Draft, số tiền khớp `rounded_total`/`grand_total` (±0.01 VND), tìm `mode_of_payment` từ `invoice.payments` (match amount hoặc dòng đầu tiên)
6. **Cập nhật:** reset `invoice.payments` → append 1 dòng (mode_of_payment + amount); `payment_status="Đã thanh toán"`, `transaction_ref`, ghi log `sepay_payment_log` (50 entry); `save()` + `submit()` → ERPNext tự set `status="Paid"`, `docstatus=1`
7. **Trả về:** `success`, `message`, `invoice_name`, `payment_code`, `transaction_id`, `amount`, `mode_of_payment`, `invoice_status`, `docstatus`, `payment_status`

**Kết quả test (Postman + ngrok):**
- Invoice chuyển sang `status="Paid"`, `docstatus=1`, `payment_status="Đã thanh toán"`
- `mode_of_payment` trả về giá trị thực tế từ POS Invoice (không hardcode)
- Gọi lại webhook (same `payment_code`) → `{success: true, already_processed: true}` (không lỗi 417, không submit lại)
- Invoice dùng `mode_of_payment` từ cột thanh toán có sẵn, không tạo Payment Entry mới

**Lưu ý:** SePay config (`api_key`, `merchant_code`, `VA`, `bank_code`) nằm chỉ ở `Branch`, không fallback `Settings` 

**Kết quả test (Postman + ngrok):**
- Invoice chuyển sang , , 
-  trả về giá trị thực tế từ POS Invoice (không hardcode)
- Gọi lại webhook (same payment_code) →  (không lỗi 417, không submit lại)
- Trừ tiền: invoice dùng  từ cột thanh toán có sẵn, không tạo Payment Entry mới

**Lưu ý quan trọng:** SePay config (, , , ) nằm chỉ ở , không fallback sang  (theo quy tách mới).


