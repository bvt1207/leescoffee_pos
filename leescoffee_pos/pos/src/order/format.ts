import type { OrderTypeValue, Stage } from "./types";

export function money(amount: number, currency = "VND"): string {
	try {
		return new Intl.NumberFormat("vi-VN", { style: "currency", currency, maximumFractionDigits: 0 }).format(
			amount || 0
		);
	} catch {
		return `${Math.round(amount || 0).toLocaleString("vi-VN")} ${currency}`;
	}
}

export const orderTypeLabel = (t: OrderTypeValue | string) => (t === "Take Away" ? "Mang đi" : "Tại quán");

/** mm:ss từ số giây. */
export function clock(seconds: number): string {
	const s = Math.max(0, Math.floor(seconds));
	return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

/** Đơn còn "đang chạy" (hiện số trên nút Đơn của tôi). */
/** Dự phòng khi server cũ không trả `group`. "failed"/"review" còn cần khách liên hệ quầy. */
export const isActiveStage = (s: Stage) =>
	s === "awaiting_payment" || s === "queued" || s === "ready" || s === "processing" || s === "failed" || s === "review";

/** Giờ:phút từ chuỗi datetime server "YYYY-MM-DD HH:MM:SS". */
export function hhmm(dt: string): string {
	const m = dt.match(/\d{2}:\d{2}/);
	return m ? m[0] : "";
}
