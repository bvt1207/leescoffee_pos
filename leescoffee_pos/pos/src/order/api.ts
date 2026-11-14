import { extractError } from "../lib/api";
import type { CartOption } from "../types";
import type {
	CustomerOrder,
	LoginResult,
	Me,
	Menu,
	OrderTypeValue,
	PaymentQr,
	Preview,
	Shop,
} from "./types";

/** Client cho api/customer_order_api.py (khách là Guest, xác thực bằng session_token). */

const API_BASE =
	(window as unknown as { ORDER_CONFIG?: { apiBase?: string } }).ORDER_CONFIG?.apiBase ||
	"/api/method/leescoffee_pos.leescoffee_pos.api.customer_order_api";

export class OrderApiError extends Error {
	status: number;
	excType: string;
	constructor(message: string, status: number, excType: string) {
		super(message);
		this.status = status;
		this.excType = excType;
	}
	/** Token phiên sai / hết hạn / bị thu hồi -> phải đăng nhập lại. */
	get sessionExpired(): boolean {
		return this.excType === "PermissionError";
	}
}

function csrfToken(): string {
	return document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") || "";
}

async function call<T>(method: string, args: Record<string, unknown> = {}): Promise<T> {
	const headers: Record<string, string> = {
		"Content-Type": "application/json",
		Accept: "application/json",
	};
	// Chỉ có khi trình duyệt đang đăng nhập Desk (Frappe chỉ kiểm CSRF với user khác Guest).
	const csrf = csrfToken();
	if (csrf && csrf !== "{{ csrf_token }}") headers["X-Frappe-CSRF-Token"] = csrf;

	let response: Response;
	try {
		response = await fetch(`${API_BASE}.${method}`, {
			method: "POST",
			credentials: "same-origin",
			headers,
			body: JSON.stringify(args),
		});
	} catch {
		throw new OrderApiError("Không kết nối được. Vui lòng kiểm tra mạng và thử lại.", 0, "NetworkError");
	}

	const text = await response.text();
	let data: Record<string, unknown> | null = null;
	try {
		data = text ? JSON.parse(text) : null;
	} catch {
		data = null;
	}

	if (!response.ok) {
		const excType = typeof data?.exc_type === "string" ? data.exc_type : "";
		throw new OrderApiError(extractError(data, response.status), response.status, excType);
	}
	return (data?.message ?? data) as T;
}

type CartItemInput = { item_code: string; qty: number; options: CartOption[] };

export const orderApi = {
	getShop: (qr_token: string) => call<Shop>("get_shop", { qr_token }),
	login: (qr_token: string, mobile: string, customer_name: string) =>
		call<LoginResult>("login", { qr_token, mobile, customer_name }),
	logout: (session_token: string) => call<{ ok: boolean }>("logout", { session_token }),
	getMe: (session_token: string) => call<Me>("get_me", { session_token }),
	getMenu: (session_token: string) => call<{ menus: Menu[]; currency: string }>("get_menu", { session_token }),
	preview: (session_token: string, items: CartItemInput[]) => call<Preview>("preview", { session_token, items }),
	createOrder: (session_token: string, items: CartItemInput[], order_type: OrderTypeValue, order_note: string) =>
		call<CustomerOrder>("create_order", { session_token, items, order_type, order_note }),
	createPaymentQr: (session_token: string, invoice_name: string) =>
		call<PaymentQr>("create_payment_qr", { session_token, invoice_name }),
	getMyOrders: (session_token: string) => call<CustomerOrder[]>("get_my_orders", { session_token }),
	getOrder: (session_token: string, invoice_name: string) =>
		call<CustomerOrder>("get_order", { session_token, invoice_name }),
};

export function errorText(err: unknown): string {
	return err instanceof Error ? err.message : String(err);
}
