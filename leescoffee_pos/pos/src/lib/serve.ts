import { useEffect } from "react";
import { notifyReady, unlockAudio } from "../order/alert";
import { useServeQueue } from "../store/serveQueue";
import type { ServeQueueItem } from "../types";
import { shortOrderNo } from "./format";

/** Nhịp poll hàng chờ phục vụ (chỉ máy có quyền Orders; dừng khi tab ẩn). */
export const SERVE_POLL_MS = 15000;

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

/** Sau một lần refresh: có đơn mới -> toast + bíp (âm thanh chỉ phát sau lần chạm đầu, xem order/alert.ts). */
export async function refreshServeQueue(): Promise<void> {
	const store = useServeQueue.getState();
	const fresh = await store.refresh();
	if (fresh.length === 0) return;
	const text = toastText(useServeQueue.getState().items, fresh);
	if (!text) return;
	useServeQueue.getState().setToast(text);
	notifyReady();
}

/**
 * Gắn MỘT lần ở App: poll get_serve_queue mỗi SERVE_POLL_MS khi `enabled` (role có quyền Orders), dừng khi tab ẩn,
 * gọi ngay khi tab hiện lại. Không chồng request (setTimeout nối tiếp + store gộp lần gọi trùng).
 */
export function useServeQueuePoller(enabled: boolean): void {
	useEffect(() => {
		const store = useServeQueue.getState();
		store.setEnabled(enabled);
		if (!enabled) return;

		let stopped = false;
		let running = false;
		let timer: number | undefined;
		const tick = async () => {
			if (stopped || running) return;
			running = true;
			if (!document.hidden) {
				try {
					await refreshServeQueue();
				} catch {
					/* lỗi mạng: thử lại ở nhịp sau */
				}
			}
			running = false;
			if (!stopped) timer = window.setTimeout(tick, SERVE_POLL_MS);
		};
		const onVisible = () => {
			if (document.hidden || stopped || running) return;
			window.clearTimeout(timer);
			void tick();
		};
		// Trình duyệt chỉ cho phát âm thanh sau khi người dùng chạm vào trang.
		const unlock = () => unlockAudio();

		void tick();
		document.addEventListener("visibilitychange", onVisible);
		window.addEventListener("pointerdown", unlock);
		return () => {
			stopped = true;
			window.clearTimeout(timer);
			document.removeEventListener("visibilitychange", onVisible);
			window.removeEventListener("pointerdown", unlock);
			useServeQueue.getState().setEnabled(false);
		};
	}, [enabled]);
}
