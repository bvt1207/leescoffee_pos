export type OrderType = "Take Away" | "Dine In";

export interface BrandInfo {
	name: string;
	logo: string;
	phone: string;
	address: string;
}

export interface PaymentMode {
	name: string;
	label: string;
	type: string;
	account: string;
	has_account: boolean;
}

export interface PosProfile {
	name: string;
	company: string;
	warehouse: string;
	currency: string;
	customer: string;
	/** Khách vãng lai của POS Profile (custom_walk_in_customer); "" = chưa cấu hình. */
	walk_in_customer?: string;
	/** false -> đơn không chọn khách bị server chặn; hiện banner. */
	walk_in_configured?: boolean;
	selling_price_list: string;
}

export type KitchenStep = "Chưa làm" | "Đã làm" | "Đã hoàn thành";

/** Mục điều hướng: sell = Bán món, orders = Đơn hàng, kitchen = Pha chế. */
export type NavKey = "sell" | "orders" | "kitchen";

export interface PosRoles {
	manager: boolean;
	cashier: boolean;
	kitchen: boolean;
}

export interface KitchenTransition {
	from: KitchenStep;
	to: KitchenStep;
}

export interface PosConfig {
	brand: BrandInfo;
	branch: string;
	profile: PosProfile;
	payment_modes: PaymentMode[];
	warnings?: string[];
	/** Phân quyền theo role, backend tính (pos_api.*_BY_ROLE). Optional để chịu được backend cũ. */
	roles?: PosRoles;
	nav?: NavKey[];
	kitchen_tabs?: KitchenStep[];
	kitchen_transitions?: KitchenTransition[];
	/** Múi giờ site (System Settings), vd. "Asia/Ho_Chi_Minh". */
	time_zone?: string;
	/** Draft kênh khác QR tự hủy sau số phút này (backend pos_invoice_hooks/order_cancel.POS_DRAFT_AUTO_CANCEL_MINUTES). */
	pos_draft_auto_cancel_minutes?: number;
}

export interface MenuSize {
	label: string;
	item_code: string;
	rate: number | null;
}

export interface MenuItem {
	idx: number;
	item_code: string;
	item_name: string;
	item_type: string;
	// Legacy: giá ở cấp item (không dùng cho UI mới — giữ tương thích).
	price?: number | null;
	// Món mới: template + sizes. sizes[0].label rỗng = 1 size (thêm thẳng giỏ).
	template?: boolean;
	name?: string;
	image?: string | null;
	sizes?: MenuSize[];
	/** Nhóm tùy chọn (MYPOS Option Group) server đã giải quyết cho món; variant dùng chung của template. */
	option_groups?: OptionGroup[];
	/** Item Group của món (template -> nhóm của template); dùng cho tab lọc ở lưới món. */
	item_group?: string | null;
}

// ---- Tùy chọn món động (MYPOS Option) — không hardcode tên nhóm/giá trị ----
export type SelectionType = "Chọn 1" | "Chọn nhiều";

export interface OptionValue {
	label: string;
	is_default: number;
	/** Phụ thu mỗi đơn vị (cộng SAU CTKM). Chỉ để hiển thị — số tiền thật do server tính. */
	extra_price?: number;
}

export interface OptionGroup {
	name: string;
	title: string;
	selection_type: SelectionType;
	required: number;
	values: OptionValue[];
}

/** Lựa chọn gửi lên server: group = name của nhóm, value = label. */
export interface CartOption {
	group: string;
	value: string;
}

/** Tùy chọn server trả về trên dòng đơn (đơn cũ: dựng từ cột sugar_level/ice_level). */
export interface LineOption {
	group: string | null;
	group_title: string;
	value: string;
	price: number;
}

export interface MenuGroup {
	name: string;
	menu_name: string;
	price_list: string;
	items: MenuItem[];
}

export interface OrderSummary {
	name: string;
	customer: string;
	customer_name: string;
	/** true = khách vãng lai của POS Profile của đơn (server tính; giao diện không so tên Customer). */
	is_walk_in?: boolean;
	order_type: OrderType;
	/** "POS" (tại quầy) | "QR" (khách tự đặt qua web) */
	order_channel?: string;
	status: string;
	docstatus: number;
	grand_total: number;
	rounded_total: number;
	amount: number;
	currency: string;
	payment_status: string;
	payment_code: string;
	custom_kitchen_status: string;
	buzzer: string;
	buzzer_number: string | null;
	creation: string;
}

export interface OrderItem {
	item_code: string;
	item_name: string;
	qty: number;
	rate: number;
	amount: number;
}

/** Chế độ màn Orders: ca đang mở (mặc định) hoặc lịch sử theo ngày (chỉ MANAGER). */
export type OrdersScope = "shift" | "history";

/** Tham số get_orders / get_orders_summary (pos_api). */
export interface OrdersQuery {
	status?: "all" | "draft" | "paid";
	scope?: OrdersScope;
	from_date?: string;
	to_date?: string;
	search?: string;
	limit?: number;
	start?: number;
}

/** get_orders_summary: bộ đếm (COUNT cùng bộ lọc) + ca đang mở + đơn Draft ca trước (chỉ MANAGER). */
export interface OrdersSummary {
	scope: OrdersScope;
	shift: { name: string; period_start_date: string } | null;
	counts: { draft: number; paid: number };
	old_drafts: number;
	from_date: string | null;
	to_date: string | null;
}

export interface OrderPayment {
	mode_of_payment: string;
	amount: number;
	type: string;
	account: string;
}

export interface OrderDetail {
	name: string;
	customer: string;
	customer_name: string;
	/** true = khách vãng lai của POS Profile của đơn (server tính; giao diện không so tên Customer). */
	is_walk_in?: boolean;
	order_type: OrderType;
	order_channel: string;
	status: string;
	docstatus: number;
	payment_status: string;
	payment_code: string;
	custom_kitchen_status: string;
	buzzer: string;
	buzzer_number: string | null;
	grand_total: number;
	amount: number;
	currency: string;
	items: OrderItem[];
	payments: OrderPayment[];
	creation: string;
	order_note?: string;
	discount_amount?: number;
	redeemed_points?: number;
	/** Phụ thu tùy chọn món đã lưu trên hóa đơn. */
	total_surcharge?: number;
}

export interface LoyaltyInfo {
	enrolled: boolean;
	program?: string;
	tier_name?: string;
	loyalty_points?: number;
	total_spent?: number;
	conversion_factor?: number;
	collection_factor?: number;
	max_redeem_points?: number;
}

export interface CreatedOrder {
	invoice_name: string;
	order_type: OrderType;
	grand_total: number;
	amount: number;
	currency: string;
	qty_sum: number;
	buzzer_number: string | null;
}

export interface QrInfo {
	invoice_name: string;
	payment_code: string;
	qr_url: string;
	amount: number;
	payment_status: string;
	idempotent: boolean;
}

export interface StatusBoardRow {
	invoice_name: string;
	customer_name: string;
	/** true = khách vãng lai của POS Profile của đơn (server tính; giao diện không so tên Customer). */
	is_walk_in?: boolean;
	order_type: OrderType;
	kitchen_status: string;
	buzzer_number: string | null;
	last_updated: string;
}

/** Một dòng màn theo dõi đơn /pos/status (server đã rút gọn; không có tên đầy đủ / SĐT / tiền / món). */
export interface OrderStatusEntry {
	/** Mã gọi khách, cùng quy tắc shortOrderNo: "#00088". */
	code: string;
	/** Tên gọi rút gọn (từ cuối, ≤ 12 ký tự); "" = chỉ hiện mã. */
	name: string;
	/** "Mang đi" | "Tại quán" | "Thẻ bàn 12". */
	label: string;
	/** Thời điểm sắp xếp (cột trái: creation; cột phải: kitchen_done_at hoặc creation). */
	at: string;
}

export interface OrderStatusBoard {
	profile: string;
	v: string;
	preparing: OrderStatusEntry[];
	ready: OrderStatusEntry[];
	/** Số đơn vượt giới hạn server (không trả chi tiết). */
	more: { preparing: number; ready: number };
}

export interface OrderStatusConfig {
	profile: string;
	/** Chỉ quản lý: POS Profile đang bật để chọn. */
	profiles: string[];
	brand: { name: string; logo: string };
}

export interface CartLine {
	item_code: string;
	item_name: string;
	item_type: string;
	price: number;
	qty: number;
	// Tùy chọn đã chọn (chuẩn hóa theo thứ tự cấu hình) + nhóm áp dụng cho món (để vẽ chip).
	options: CartOption[];
	option_groups: OptionGroup[];
	// Size đã chọn (label + item_code variant).
	size?: string | null;
	// Price List của menu đang dùng (khi tạo đơn).
	price_list?: string;
	note?: string;
}

export interface CustomerOption {
	name: string;
	customer_name: string;
	mobile_no?: string | null;
}

export interface OrderItem {
	item_code: string;
	item_name: string;
	qty: number;
	rate: number;
	amount: number;
	// Cột cũ (chỉ đọc, đơn cũ) — hiển thị dùng `options`.
	sugar_level?: string;
	ice_level?: string;
	options?: LineOption[];
	size?: string;
	price_list_rate?: number;
	discount_percentage?: number;
	pricing_rules?: string[];
}

export interface PricingPreviewItem {
	item_code: string;
	qty: number;
	price_list_rate: number;
	rate: number;
	discount_percentage: number;
	saved: number;
	rules: { name: string; title: string }[];
	is_free_item: number;
}

export interface PricingPreview {
	items: PricingPreviewItem[];
	total_before: number;
	total_discount_rules: number;
	loyalty_discount: number;
	/** Tổng phụ thu tùy chọn món (dòng "Phụ thu" kiểu Actual, sau CTKM). */
	total_surcharge?: number;
	grand_total: number;
	max_redeem_points: number;
}

export interface KitchenItem {
	item_code: string;
	item_name: string;
	qty: number;
	sugar_level?: string;
	ice_level?: string;
	options?: LineOption[];
}

export interface KitchenOrder {
	name: string;
	customer_name: string;
	/** true = khách vãng lai của POS Profile của đơn (server tính; giao diện không so tên Customer). */
	is_walk_in?: boolean;
	order_type: OrderType;
	order_channel?: string;
	kitchen_status: KitchenStep;
	buzzer_number: string | null;
	order_note: string | null;
	creation: string;
	items: KitchenItem[];
}
/** Đơn chờ phục vụ (get_serve_queue): tại quầy, đã thanh toán, pha chế "Đã làm". Dine In = mang tới thẻ bàn. */
export interface ServeQueueItem {
	name: string;
	order_type: OrderType;
	/** Số thẻ bàn (Dine In); Take Away = null. */
	buzzer_number: string | null;
	/** "" khi khách vãng lai của POS Profile — hiện mã ngắn của đơn. */
	customer_name: string;
	/** true = khách vãng lai của POS Profile của đơn (server tính; giao diện không so tên Customer). */
	is_walk_in?: boolean;
	item_count: number;
	/** 2 món đầu, dạng "Tên xN". */
	items_preview: string[];
	/** Số dòng món còn lại ngoài items_preview. */
	more_lines: number;
	done_at: string | null;
	/** Số giây từ lúc "Đã làm" tới lúc server trả (không dựa vào đồng hồ máy quầy). */
	waiting_seconds: number;
}
/** Thẻ bàn (tên kỹ thuật buzzer, DocType MYPOS Buzzer). status/available tính theo đơn còn giữ. */
export interface BuzzerOption {
	name: string;
	buzzer_number: string;
	status: string;
	branch: string;
	available: boolean;
	used_by: string | null;
}
// ---------------------------------------------------------------------------
// Màn khách (/pos/customer) — customer_display_api.py
// ---------------------------------------------------------------------------

export interface CustomerDisplayConfig {
	brand: Partial<BrandInfo>;
	currency: string;
	pos_profile: string;
	banners: { title: string; image: string }[];
}

export type CustomerDisplayPhase = "idle" | "cart" | "order" | "qr" | "paid";

export interface CustomerDisplayLine {
	item_name: string;
	size: string;
	qty: number;
	options: LineOption[];
	price_list_rate: number;
	rate: number;
	/** Thành tiền dòng đã gồm phụ thu tùy chọn (server tính). */
	amount: number;
	is_free_item: number;
}

export interface CustomerDisplayOrder {
	invoice?: string;
	order_type?: string;
	currency: string;
	lines: CustomerDisplayLine[];
	totals: {
		total_before: number;
		total_discount_rules: number;
		total_surcharge: number;
		loyalty_discount: number;
		redeemed_points: number;
		grand_total: number;
		amount_due: number;
		amount_total: number;
	};
	customer: { name: string; is_walk_in: boolean; tier_name: string; loyalty_points: number | null };
	paid?: boolean;
}

export interface CustomerDisplayState {
	v: number;
	unchanged?: boolean;
	phase?: CustomerDisplayPhase;
	order?: CustomerDisplayOrder;
	qr?: { qr_url: string; amount: number; payment_code: string };
	paid_at?: string;
}
