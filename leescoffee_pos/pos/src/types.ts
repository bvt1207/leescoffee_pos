export type OrderType = "Take Away" | "Dine In";

export interface BrandInfo {
	name: string;
	logo: string;
	banner: string;
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
}

// ---- Tùy chọn món động (MYPOS Option) — không hardcode tên nhóm/giá trị ----
export type SelectionType = "Chọn 1" | "Chọn nhiều";

export interface OptionValue {
	label: string;
	is_default: number;
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
	order_type: OrderType;
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
	order_type: OrderType;
	kitchen_status: string;
	buzzer_number: string | null;
	last_updated: string;
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
	order_type: OrderType;
	kitchen_status: KitchenStep;
	buzzer_number: string | null;
	order_note: string | null;
	creation: string;
	items: KitchenItem[];
}
export interface BuzzerOption {
	name: string;
	buzzer_number: string;
	status: string;
	branch: string;
	available: boolean;
	used_by: string | null;
}