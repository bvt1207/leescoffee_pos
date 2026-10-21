import type {
	CreatedOrder,
	OrderDetail,
	OrderSummary,
	PosConfig,
	QrInfo,
	StatusBoardRow,
} from "../types";

const API_BASE =
	(window as unknown as { POS_CONFIG?: { apiBase?: string; csrfToken?: string } }).POS_CONFIG?.apiBase ||
	"/api/method/leescoffee_pos.leescoffee_pos.api.pos_api";

function csrfToken(): string {
	const meta = document.querySelector('meta[name="csrf-token"]');
	return (
		meta?.getAttribute("content") ||
		(window as unknown as { POS_CONFIG?: { csrfToken?: string } }).POS_CONFIG?.csrfToken ||
		""
	);
}

function extractError(data: unknown, status: number): string {
	if (!data || typeof data !== "object") return `Lỗi ${status}`;
	const raw = (data as Record<string, unknown>)._server_messages;
	if (typeof raw === "string") {
		try {
			const parsed = JSON.parse(raw);
			if (Array.isArray(parsed) && parsed.length) {
				return parsed
					.map((m) => m?.message)
					.filter((m): m is string => typeof m === "string" && m)
					.join(" | ");
			}
		} catch {
			/* ignore */
		}
	} else if (Array.isArray(raw)) {
		return raw
			.map((m) => m?.message)
			.filter((m): m is string => typeof m === "string" && m)
			.join(" | ");
	}

	if ((data as Record<string, unknown>).exception) {
		return String((data as Record<string, unknown>).exception).split("\n")[0];
	}

	if (typeof (data as Record<string, unknown>).message === "string") {
		return String((data as Record<string, unknown>).message);
	}

	return `Lỗi ${status}`;
}

export async function call<T>(method: string, args: Record<string, unknown> = {}): Promise<T> {
	let response: Response;
	try {
		response = await fetch(`${API_BASE}.${method}`, {
			method: "POST",
			credentials: "same-origin",
			headers: {
				"Content-Type": "application/json",
				Accept: "application/json",
				"X-Frappe-CSRF-Token": csrfToken(),
			},
			body: JSON.stringify(args),
		});
	} catch {
		throw new Error("Không kết nối được tới máy chủ POS.");
	}

	const text = await response.text();
	let data: unknown = null;
	if (text) {
		try {
			data = JSON.parse(text);
		} catch {
			data = null;
		}
	}

	if (!response.ok) {
		throw new Error(extractError(data, response.status));
	}

	// Frappe v16: hàm whitelisted trả về dict → body = {"message": {...}}
	// Giá fallback: {"data": {...}} hoặc dict thẳng.
	const payload =
		data && typeof data === "object"
			? (data as Record<string, unknown>)
			: (data as T);

	if (payload && typeof payload === "object") {
		const record = payload as Record<string, unknown>;
		if (record.message !== undefined) return record.message as T;
		if (record.data !== undefined) return record.data as T;
	}

	return payload as T;
}

export const api = {
	getPosConfig: () => call<PosConfig>("get_pos_config"),
	getMenuItems: () => call<unknown[]>("get_menu_items"),
	getBuzzers: (branch_name?: string) => call<unknown[]>("get_buzzers", { branch_name }),
	createDraftOrder: (p: {
		items: Array<{ item_code: string; qty: number; uom?: string; warehouse?: string }>;
		order_type: string;
		customer_name?: string;
		mode_of_payment?: string;
		branch_name?: string;
	}) => call<CreatedOrder>("create_draft_order", p),
	getOrders: (status: "all" | "draft" | "paid") => call<OrderSummary[]>("get_orders", { status }),
	getOrderDetail: (invoice_name: string) => call<OrderDetail>("get_order_detail", { invoice_name }),
	payCash: (invoice_name: string) => call<{ invoice_name: string; status: string; payment_status: string; amount: number; currency: string }>("pay_cash", { invoice_name }),
	generateQr: (invoice_name: string) => call<QrInfo>("generate_qr", { invoice_name }),
	confirmPickup: (invoice_name: string) => call<{ invoice_name: string; buzzer_number: string | null; message: string }>("confirm_pickup", { invoice_name }),
	getStatusBoard: () => call<StatusBoardRow[]>("get_status_board"),
};
