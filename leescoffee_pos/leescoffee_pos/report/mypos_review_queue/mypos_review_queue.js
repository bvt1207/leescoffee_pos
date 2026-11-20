// Script Report "MYPOS Review Queue" (Đơn cần xử lý): chỉ xem / tìm. Xử lý đơn: mở đơn -> nút "Xử lý đơn" (pos_invoice.js).
frappe.query_reports["MYPOS Review Queue"] = {
	filters: [
		{ fieldname: "pos_profile", label: __("POS Profile"), fieldtype: "Link", options: "POS Profile" },
		{ fieldname: "search", label: __("Mã đơn / tên khách"), fieldtype: "Data" },
		{ fieldname: "overdue_only", label: __("Chỉ đơn quá 24 giờ"), fieldtype: "Check" },
	],
};
