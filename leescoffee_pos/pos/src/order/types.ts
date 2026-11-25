import type { CartOption, LineOption, OptionGroup } from "../types";

/** Kiểu dữ liệu của web đặt món QR (khớp api/customer_order_api.py). */

export type OrderTypeValue = "Take Away" | "Dine In";

export interface Brand {
	name: string;
	logo: string;
	phone: string;
	address: string;
}

export interface Shop {
	brand: Brand;
	/** Ảnh đầu trang đăng nhập: MYPOS Banner public đầu tiên ('' = không có). */
	banner: string;
	is_open: boolean;
	order_types: OrderTypeValue[];
	pay_window_minutes: number;
}

export interface LoginResult {
	session_token: string;
	expires_at: number;
	customer_name: string;
	/** Khóa mờ (HMAC khách + mã QR) để lưu giỏ ở localStorage. */
	cart_key: string;
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
	cart_key: string;
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
	total_surcharge?: number;
	grand_total: number;
	loyalty: Loyalty;
}

/** Trạng thái hiển thị cho khách (server quy đổi từ trạng thái pha chế; giá trị lạ -> "processing"). */
export type Stage =
	| "awaiting_payment"
	| "expired"
	| "queued"
	| "ready"
	| "done"
	| "closed"
	| "failed"
	| "review"
	| "processing";

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
	/** Thông điệp nổi bật cho khách (đơn không thực hiện được / chờ quầy xác nhận); rỗng nếu không có. */
	stage_message?: string;
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
	/** Chỉ có ở get_my_orders: "active" (Đang xử lý) | "history" (Lịch sử). */
	group?: "active" | "history";
}

export interface PaymentQr {
	invoice_name: string;
	qr_url: string;
	payment_code: string;
	amount: number;
	expires_at: string;
	expires_in: number;
}
