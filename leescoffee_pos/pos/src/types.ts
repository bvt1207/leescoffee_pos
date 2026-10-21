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

export interface MenuItem {
	idx: number;
	item_code: string;
	item_name: string;
	item_type: string;
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
}
