import type { CartOption, LineOption, OptionGroup } from "../types";

/** Kiểu dữ liệu của web đặt món QR (khớp api/customer_order_api.py). */

export type OrderTypeValue = "Take Away" | "Dine In";

export interface Brand {
	name: string;
	logo: string;
	banner: string;
	phone: string;
	address: string;
}

export interface Shop {
	brand: Brand;
	is_open: boolean;
	order_types: OrderTypeValue[];
	pay_window_minutes: number;
}

export interface LoginResult {
	session_token: string;
	expires_at: number;
	customer_name: string;
	shop: Shop;
}

export interface Loyalty {
	enrolled: boolean;
	tier_name?: string;
	loyalty_points?: number;
	redeem_enabled: boolean;
}

export interface Me {
	customer_name: string;
	loyalty: Loyalty;
	shop: Shop;
}

export interface SizeOption {
	label: string;
	item_code: string;
	rate: number;
}

export interface MenuItem {
	name: string;
	image: string | null;
	template: boolean;
	sizes: SizeOption[];
	option_groups: OptionGroup[];
}

export interface Menu {
	name: string;
	menu_name: string;
	items: MenuItem[];
}

export interface CartLine {
	key: string;
	item_name: string;
	size_label: string;
	item_code: string;
	rate: number;
	qty: number;
	options: CartOption[];
	option_groups: OptionGroup[];
	image: string | null;
}

export interface PreviewLine {
	item_code: string;
	qty: number;
	price_list_rate: number;
	rate: number;
	discount_percentage: number;
	saved: number;
	rules: Array<{ title: string }>;
	is_free_item: number;
}

export interface Preview {
	items: PreviewLine[];
	total_before: number;
	total_discount_rules: number;
	loyalty_discount: number;
	grand_total: number;
	loyalty: Loyalty;
}

export type Stage = "awaiting_payment" | "expired" | "queued" | "ready" | "done";

export interface OrderLine {
	item_name: string;
	size: string;
	qty: number;
	amount: number;
	options: LineOption[];
}

export interface CustomerOrder {
	invoice_name: string;
	order_type: OrderTypeValue;
	stage: Stage;
	stage_label: string;
	kitchen_status: string;
	customer_name: string;
	amount: number;
	currency: string;
	creation: string;
	expires_at: string | null;
	expires_in: number | null;
	has_payment_qr: boolean;
	order_note: string;
	items: OrderLine[];
}

export interface PaymentQr {
	invoice_name: string;
	qr_url: string;
	payment_code: string;
	amount: number;
	expires_at: string;
	expires_in: number;
}
