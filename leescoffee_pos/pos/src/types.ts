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

export interface PosConfig {
	brand: BrandInfo;
	branch: string;
	profile: PosProfile;
	payment_modes: PaymentMode[];
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
	// Đường / Đá: 50 | 70 | 100 (%), default 100.
	ice?: number;
	sugar?: number;
	// Size đã chọn (label + item_code variant).
	size?: string | null;
	// Price List của menu đang dùng (khi tạo đơn).
	price_list?: string;
	// TODO: backend custom field — ice/sugar/note chưa gửi server, chỉ giữ state.
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
	sugar_level?: string;
	ice_level?: string;
}

export interface KitchenItem {
	item_code: string;
	item_name: string;
	qty: number;
	sugar_level: string;
	ice_level: string;
}

export interface KitchenOrder {
	name: string;
	customer_name: string;
	order_type: OrderType;
	kitchen_status: "Chưa làm" | "Đã làm" | "Đã hoàn thành";
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