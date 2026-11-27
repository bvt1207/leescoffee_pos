import { useEffect } from "react";
import { usePosRefresh } from "./changes";
import { notifyReady, unlockAudio } from "../order/alert";
import { useServeQueue } from "../store/serveQueue";
import { pushToast } from "../store/toasts";
import type { ServeQueueItem } from "../types";
import { shortOrderNo } from "./format";

/** Nhịp hỏi phiên bản thay đổi khi chỉ có hàng chờ phục vụ cần (máy có role CASHIER; dừng khi tab ẩn). */
export const SERVE_POLL_MS = 15000;
/** Lưới an toàn hàng chờ: tải lại dù phiên bản không đổi. */
export const SERVE_SAFETY_MS = 120000;

const isDineIn = (o: ServeQueueItem) => o.order_type === "Dine In";

/** "Bàn 07" (Dine In có thẻ bàn) hoặc mã ngắn "#00066". */
export function serveTarget(o: ServeQueueItem): string {
	return isDineIn(o) && o.buzzer_number ? `Bàn ${o.buzzer_number}` : shortOrderNo(o.name);
}

/** Câu toast cho đơn mới: "Bàn 07 sẵn sàng phục vụ" / "#00066 · Gọi khách lấy món"; nhiều đơn -> gộp. */
function toastText(items: ServeQueueItem[], fresh: string[]): string {
	const rows = items.filter((o) => fresh.includes(o.name));
	if (rows.length === 0) return "";
	if (rows.length > 1) return `${rows.length} đơn chờ phục vụ: ${rows.map(serveTarget).join(", ")}`;
	const o = rows[0];
	return isDineIn(o) ? `${serveTarget(o)} sẵn sàng phục vụ` : `${serveTarget(o)} · Gọi khách lấy món`;
}

/** Toast hàng chờ hiển thị lâu hơn toast xác nhận (thông báo bền là chấm đỏ ở "Pha chế"). */
export const SERVE_TOAST_MS = 8000;

/** Sau một lần refresh: có đơn mới -> toast + bíp (âm thanh chỉ phát sau lần chạm đầu, xem order/alert.ts). */
export async function refreshServeQueue(quiet: string[] = []): Promise<void> {
	const store = useServeQueue.getState();
	// quiet: đơn chính máy này vừa chuyển "Đã làm" — màn Pha chế đã có toast xác nhận, không báo trùng lớp thứ hai.
	const fresh = await store.refresh(quiet);
	if (fresh.length === 0) return;
	const text = toastText(useServeQueue.getState().items, fresh);
	if (!text) return;
	// Khóa theo danh sách đơn: cùng sự kiện tới từ cả realtime lẫn poll chỉ ra MỘT toast (store/toasts.ts).
	pushToast(text, { key: `serve:${[...fresh].sort().join(",")}`, ms: SERVE_TOAST_MS });
	notifyReady();
}

/**
 * Gắn MỘT lần ở App khi `enabled` (user có role POS CASHIER). Từ 2026-11-25: không poll get_serve_queue mỗi SERVE_POLL_MS nữa —
 * hỏi phiên bản thay đổi (lib/changes.ts, server chỉ đọc Redis) mỗi SERVE_POLL_MS (hoặc nhanh hơn nếu màn khác cần),
 * chỉ tải hàng chờ khi phiên bản đổi + lưới an toàn SERVE_SAFETY_MS. Tab ẩn -> dừng; hiện lại -> hỏi ngay.
 */
export function useServeQueuePoller(enabled: boolean): void {
	// Bật store TRƯỚC usePosRefresh (effect chạy theo thứ tự khai báo): refresh() bỏ qua khi store tắt.
	useEffect(() => {
		useServeQueue.getState().setEnabled(enabled);
		if (!enabled) return;
		// Trình duyệt chỉ cho phát âm thanh sau khi người dùng chạm vào trang.
		const unlock = () => unlockAudio();
		window.addEventListener("pointerdown", unlock);
		return () => {
			window.removeEventListener("pointerdown", unlock);
			useServeQueue.getState().setEnabled(false);
		};
	}, [enabled]);

	usePosRefresh(() => refreshServeQueue(), { enabled, intervalMs: SERVE_POLL_MS, safetyMs: SERVE_SAFETY_MS });
}
