// POS Opening Entry (Desk): thu ngân chỉ mở ca cho chính mình.
// Phiếu mới -> Cashier = người đăng nhập; không phải quản lý -> khóa trường Cashier.
// Chỉ hỗ trợ giao diện; chốt chặn thật ở server (doctype/pos_shift_hooks/pos_shift_hooks.py).
frappe.ui.form.on("POS Opening Entry", {
	onload(frm) {
		if (frm.is_new() && !frm.doc.user) {
			frm.set_value("user", frappe.session.user);
		}
	},
	refresh(frm) {
		const isManager = frappe.user.has_role(["POS MANAGER", "System Manager", "Administrator"]);
		if (!isManager && frm.doc.docstatus === 0) {
			if (frm.doc.user !== frappe.session.user) {
				frm.set_value("user", frappe.session.user);
			}
			frm.set_df_property("user", "read_only", 1);
		}
	},
});
