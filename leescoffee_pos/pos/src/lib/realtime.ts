import { useEffect, useRef } from "react";
import { io, type Socket } from "socket.io-client";

/**
 * Kết nối socket.io của Frappe (tiến trình `socketio` của bench) để nhận publish_realtime(..., user=<user>).
 *
 * Cách dựng địa chỉ theo client gốc của Frappe (frappe/public/js/frappe/socketio_client.js):
 * - Namespace = tên site ("/<site>"), path "/socket.io", xác thực bằng cookie phiên (withCredentials).
 * - dev server (bench start): socket ở cổng riêng `socketio_port`; production (nginx): cùng origin.
 * [Unverified] Chưa chạy thử trên bench Frappe v16 của dự án. Kết nối lỗi -> chỉ còn poll, màn khách vẫn đúng.
 */
interface RealtimeConfig {
	site?: string;
	port?: number;
	devServer?: number | boolean;
}

function realtimeConfig(): RealtimeConfig {
	return (window as unknown as { POS_CONFIG?: { realtime?: RealtimeConfig } }).POS_CONFIG?.realtime || {};
}

function socketUrl(cfg: RealtimeConfig): string | null {
	if (!cfg.site) return null;
	const host = cfg.devServer
		? `${window.location.protocol}//${window.location.hostname}:${cfg.port || 9000}`
		: window.location.origin;
	return `${host}/${cfg.site}`;
}

/** Nghe một sự kiện realtime; `onEvent` đọc qua ref (đổi closure không kết nối lại). */
export function useRealtimeEvent(event: string, onEvent: (data: unknown) => void, enabled = true) {
	const handler = useRef(onEvent);
	handler.current = onEvent;

	useEffect(() => {
		if (!enabled) return;
		const url = socketUrl(realtimeConfig());
		if (!url) return;
		let socket: Socket | null = null;
		try {
			socket = io(url, {
				path: "/socket.io",
				withCredentials: true,
				reconnectionAttempts: Infinity,
				reconnectionDelayMax: 30000,
			});
			socket.on(event, (data: unknown) => handler.current(data));
			// Kết nối lại sau khi mất mạng: báo để màn khách lấy trạng thái ngay (có thể đã lỡ sự kiện).
			socket.on("connect", () => handler.current(null));
		} catch {
			socket = null;
		}
		return () => {
			socket?.off(event);
			socket?.disconnect();
		};
	}, [event, enabled]);
}
