// Hiển thị ảnh QR + nút in cho mã đặt món (MYPOS Order QR).
const MYPOS_QR_METHOD =
	"mypos.mypos.doctype.mypos_order_qr.mypos_order_qr.get_qr_image";

function mypos_qr_render(frm, data) {
	const field = frm.get_field("qr_preview");
	if (!field) return;
	const url = frappe.utils.escape_html(data.url || "");
	const img = data.svg
		? `<div class="mypos-qr-box" style="width:240px;max-width:100%">${data.svg}</div>`
		: `<div class="text-muted">${__("Không sinh được ảnh QR (thiếu thư viện pyqrcode). Dùng URL bên dưới.")}</div>`;
	const off = data.enabled
		? ""
		: `<div class="text-danger" style="margin-bottom:8px">${__("Mã đang tắt: khách quét sẽ không đặt được món.")}</div>`;
	field.$wrapper.html(`${off}${img}<div style="margin-top:8px;word-break:break-all"><a href="${url}" target="_blank" rel="noopener">${url}</a></div>`);
	field.$wrapper.find("svg").css({ width: "100%", height: "auto" });
}

function mypos_qr_print(data) {
	const w = window.open("", "_blank");
	if (!w) {
		frappe.msgprint(__("Trình duyệt chặn cửa sổ in. Hãy cho phép popup."));
		return;
	}
	const url = frappe.utils.escape_html(data.url || "");
	const branch = frappe.utils.escape_html(data.branch || "");
	w.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>QR ${branch}</title>
<style>body{font-family:sans-serif;text-align:center;margin:24px}svg{width:70mm;height:70mm}
p{font-size:12px;word-break:break-all}</style></head><body>
<h2>${__("Quét để đặt món")}</h2>${data.svg || ""}<p>${url}</p><p>${branch}</p>
<script>window.onload=function(){window.print();}<\/script></body></html>`);
	w.document.close();
}

frappe.ui.form.on("MYPOS Order QR", {
	refresh(frm) {
		const field = frm.get_field("qr_preview");
		if (frm.is_new()) {
			if (field) field.$wrapper.html(`<div class="text-muted">${__("Lưu để sinh mã QR.")}</div>`);
			return;
		}
		frappe.call({ method: MYPOS_QR_METHOD, args: { name: frm.doc.name } }).then((r) => {
			const data = r.message || {};
			mypos_qr_render(frm, data);
			frm.add_custom_button(__("In mã QR"), () => mypos_qr_print(data));
			frm.add_custom_button(__("Sao chép URL"), () => frappe.utils.copy_to_clipboard(data.url || ""));
		});
	},
});
