// POS Invoice (Desk): nút "Xử lý đơn" cho quản lý với đơn cần xử lý ("Đã đóng ca chưa xử lý" hoặc "Cần xem lại").
// Chỉ gọi pos_api.resolve_open_order (luồng xem lại ở server: lý do bắt buộc, needs_review = 0, comment) — không có logic thứ hai.
(() => {
	const MANAGER_ROLES = ["POS MANAGER", "System Manager", "Administrator"];
	const SHIFT_CLOSED = "Đã đóng ca chưa xử lý";
	const OUTCOMES = ["Đã hoàn thành", "Không thực hiện được", "Khách không nhận"];

	frappe.ui.form.on("POS Invoice", {
		refresh(frm) {
			const doc = frm.doc;
			const needsReview = doc.custom_kitchen_status === SHIFT_CLOSED || !!doc.needs_review;
			if (doc.docstatus !== 1 || !needsReview || !frappe.user.has_role(MANAGER_ROLES)) return;
			frm.add_custom_button(__("Xử lý đơn"), () => {
				frappe.prompt(
					[
						{
							fieldname: "outcome",
							fieldtype: "Select",
							label: __("Kết cục"),
							options: OUTCOMES.join("\n"),
							reqd: 1,
						},
						{ fieldname: "reason", fieldtype: "Small Text", label: __("Lý do"), reqd: 1 },
					],
					(values) => {
						frappe.call({
							method: "leescoffee_pos.leescoffee_pos.api.pos_api.resolve_open_order",
							args: { invoice_name: doc.name, outcome: values.outcome, reason: values.reason },
							freeze: true,
							callback: () => {
								frappe.show_alert({ message: __("Đã xử lý đơn {0}.", [doc.name]), indicator: "green" });
								frm.reload_doc();
							},
						});
					},
					__("Xử lý đơn {0}", [doc.name]),
					__("Xác nhận")
				);
			});
		},
	});
})();
