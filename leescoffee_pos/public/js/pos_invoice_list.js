// Danh sách POS Invoice (Desk): 3 nút lọc nhanh cho quản lý (2026-11-23). Không lọc ngày / ca.
// Bổ sung vào listview_settings sẵn có của ERPNext (giữ màu trạng thái, onload cũ) — không ghi đè.
(() => {
	const MANAGER_ROLES = ["POS MANAGER", "System Manager", "Administrator"];
	const DT = "POS Invoice";
	const OPEN_KITCHEN = ["Chưa làm", "Đã làm"];

	const QUICK_FILTERS = [
		{ label: __("Nháp cần hủy"), filters: [[DT, "docstatus", "=", 0]] },
		{
			label: __("Chưa pha chế"),
			filters: [
				[DT, "docstatus", "=", 1],
				[DT, "is_return", "=", 0],
				[DT, "custom_kitchen_status", "in", OPEN_KITCHEN],
			],
		},
		{
			// Gộp hai nhóm trên: bộ lọc list view chỉ nối AND -> Draft có trạng thái pha chế rỗng nên khớp "".
			label: __("Đơn còn dở"),
			filters: [
				[DT, "docstatus", "in", [0, 1]],
				[DT, "is_return", "=", 0],
				[DT, "custom_kitchen_status", "in", ["", ...OPEN_KITCHEN]],
			],
		},
	];

	function apply(listview, filters) {
		listview.filter_area
			.clear(false)
			.then(() => listview.filter_area.add(filters, false))
			.then(() => listview.refresh());
	}

	const settings = (frappe.listview_settings[DT] = frappe.listview_settings[DT] || {});
	const previousOnload = settings.onload;
	settings.onload = function (listview) {
		if (typeof previousOnload === "function") previousOnload.call(this, listview);
		if (!frappe.user.has_role(MANAGER_ROLES)) return;
		QUICK_FILTERS.forEach((q) => {
			listview.page.add_inner_button(q.label, () => apply(listview, q.filters), __("Lọc nhanh"));
		});
	};
})();
