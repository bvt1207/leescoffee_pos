// POS Invoice (Desk), chỉ quản lý — xử lý TỪNG đơn, mỗi đơn một lý do (2026-11-23):
// - Đơn nháp: nút "Hủy đơn" -> pos_api.cancel_draft_order (cùng API màn Orders; đơn chuyển Cancelled + lý do).
// - Đơn đã thu tiền đang Chưa làm / Đã làm: nút "Xử lý đơn" -> pos_api.resolve_open_order (lý do bắt buộc).
// Chốt chặn thật ở server; nút chỉ là giao diện.
(() => {
	const MANAGER_ROLES = ["POS MANAGER", "System Manager", "Administrator"];
	const OPEN_STATUSES = ["", "Chưa làm", "Đã làm"];
	const OUTCOMES = ["Đã hoàn thành", "Không thực hiện được", "Khách không nhận"];
	const CANCEL_REASONS = ["Khách đổi ý", "Đặt nhầm", "Khách không lấy", "Khác"];
	const API = "mypos.mypos.api.pos_api.";

	function cancelDraft(frm) {
		const doc = frm.doc;
		const waiting = doc.payment_status === "Đang chờ";
		const fields = [
			{ fieldname: "reason", fieldtype: "Select", label: __("Lý do hủy"), options: CANCEL_REASONS.join("\n"), reqd: 1 },
			{
				fieldname: "note",
				fieldtype: "Small Text",
				label: __("Ghi chú"),
				mandatory_depends_on: "eval:doc.reason=='Khác'",
				description: __("Bắt buộc khi chọn \"Khác\"."),
			},
		];
		if (waiting) {
			fields.push({
				fieldname: "confirm_unpaid",
				fieldtype: "Check",
				label: __("Đơn đã sinh mã QR — tôi đã kiểm tra khách chưa chuyển tiền"),
				reqd: 1,
			});
		}
		const dialog = new frappe.ui.Dialog({
			title: __("Hủy đơn {0}", [doc.name]),
			fields,
			primary_action_label: __("Hủy đơn"),
			primary_action(values) {
				if (values.reason === "Khác" && !(values.note || "").trim()) {
					frappe.msgprint(__("Lý do \"Khác\": nhập ghi chú."));
					return;
				}
				if (waiting && !values.confirm_unpaid) {
					frappe.msgprint(__("Xác nhận khách chưa chuyển tiền trước khi hủy."));
					return;
				}
				frappe.call({
					method: API + "cancel_draft_order",
					args: {
						invoice_name: doc.name,
						force: waiting ? 1 : 0,
						reason: values.reason,
						note: (values.note || "").trim(),
					},
					freeze: true,
					callback: () => {
						dialog.hide();
						frappe.show_alert({ message: __("Đã hủy đơn {0}.", [doc.name]), indicator: "orange" });
						frm.reload_doc();
					},
				});
			},
		});
		dialog.set_message(__("Đơn sẽ bị hủy và lưu lại để đối soát."));
		dialog.show();
	}

	function resolveOrder(frm) {
		const doc = frm.doc;
		frappe.prompt(
			[
				{ fieldname: "outcome", fieldtype: "Select", label: __("Kết cục"), options: OUTCOMES.join("\n"), reqd: 1 },
				{ fieldname: "reason", fieldtype: "Small Text", label: __("Lý do xử lý pha chế"), reqd: 1 },
			],
			(values) => {
				frappe.call({
					method: API + "resolve_open_order",
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
	}

	frappe.ui.form.on("POS Invoice", {
		refresh(frm) {
			const doc = frm.doc;
			if (frm.is_new() || doc.is_return || !frappe.user.has_role(MANAGER_ROLES)) return;
			if (doc.docstatus === 0) {
				frm.add_custom_button(__("Hủy đơn"), () => cancelDraft(frm));
			} else if (doc.docstatus === 1 && OPEN_STATUSES.includes(doc.custom_kitchen_status || "")) {
				frm.add_custom_button(__("Xử lý đơn"), () => resolveOrder(frm));
			}
		},
	});
})();
