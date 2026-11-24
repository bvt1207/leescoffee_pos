// POS Profile (Desk): field "Khách vãng lai" (custom_walk_in_customer) chỉ gợi ý Customer đang bật (2026-11-24).
// Chỉ hỗ trợ giao diện; chốt chặn thật ở server (pos_profile_hooks.validate: tồn tại, không disabled, không Loyalty Program).
frappe.ui.form.on("POS Profile", {
	setup(frm) {
		frm.set_query("custom_walk_in_customer", () => ({ filters: { disabled: 0 } }));
	},
});
