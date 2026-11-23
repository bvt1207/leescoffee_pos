// POS Opening Entry (Desk): thu ngân chỉ mở ca cho chính mình.
// Phiếu mới -> Cashier = người đăng nhập; không phải quản lý -> khóa trường Cashier.
// Không còn "Đóng ca bắt buộc" (bỏ 2026-11-23): quản lý hủy / xử lý từng đơn trên POS Invoice rồi mới đóng ca.
// Chỉ hỗ trợ giao diện; chốt chặn thật ở server (pos_shift_hooks.py).
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
	},
});
