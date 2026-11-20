// POS Opening Entry (Desk): thu ngân chỉ mở ca cho chính mình.
// Phiếu mới -> Cashier = người đăng nhập; không phải quản lý -> khóa trường Cashier.
// Quản lý: nút "Đóng ca bắt buộc" trên ca đang mở (hủy mọi đơn Draft kèm lý do + nhật ký, rồi đóng ca).
// Chỉ hỗ trợ giao diện; chốt chặn thật ở server (pos_shift_hooks.py, pos_api.force_close_shift).
const MYPOS_MANAGER_ROLES = ["POS MANAGER", "System Manager", "Administrator"];

frappe.ui.form.on("POS Opening Entry", {
	onload(frm) {
		if (frm.is_new() && !frm.doc.user) {
			frm.set_value("user", frappe.session.user);
		}
	},
	refresh(frm) {
		const isManager = frappe.user.has_role(MYPOS_MANAGER_ROLES);
		if (!isManager && frm.doc.docstatus === 0) {
			if (frm.doc.user !== frappe.session.user) {
				frm.set_value("user", frappe.session.user);
			}
			frm.set_df_property("user", "read_only", 1);
		}
		if (isManager && frm.doc.docstatus === 1 && frm.doc.status === "Open") {
			frm.add_custom_button(__("Đóng ca bắt buộc"), () => mypos_force_close(frm));
		}
	},
});

function mypos_force_close(frm) {
	frappe.prompt(
		[
			{
				fieldname: "reason",
				fieldtype: "Small Text",
				label: __("Lý do đóng ca bắt buộc"),
				reqd: 1,
				description: __("Mọi đơn chưa thanh toán của ca sẽ bị hủy (ghi nhật ký hủy) rồi ca được đóng."),
			},
		],
		(values) => {
			frappe.call({
				method: "leescoffee_pos.leescoffee_pos.api.pos_api.force_close_shift",
				args: { opening_entry: frm.doc.name, reason: values.reason },
				freeze: true,
				freeze_message: __("Đang đóng ca…"),
				callback: (r) => {
					const res = r.message || {};
					frappe.show_alert({
						message: __("Đã đóng ca, hủy {0} đơn chưa thanh toán.", [(res.cancelled || []).length]),
						indicator: "green",
					});
					if (res.closing_entry) {
						frappe.set_route("Form", "POS Closing Entry", res.closing_entry);
					} else {
						frm.reload_doc();
					}
				},
			});
		},
		__("Đóng ca bắt buộc"),
		__("Hủy đơn và đóng ca")
	);
}
