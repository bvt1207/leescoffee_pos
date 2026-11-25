import { useEffect, useRef } from "react";
import { io, type Socket } from "socket.io-client";

/**
 * Kết nối socket.io của Frappe (tiến trình `socketio` của bench) để nhận publish_realtime(..., user=<user>).
 *
 * Cách dựng địa chỉ theo client gốc của Frappe (frappe/public/js/frappe/socketio_client.js):
 * - Namespace = tên site ("/<site>"), path "/socket.io", xác thực bằng cookie phiên (withCredentials).
 * - dev server (bench start): socket ở cổng riêng `socketio_port`; production (nginx): cùng origin.
 * Đã chạy trên bench DEV v16.30 (2026-11-25): mở site bằng `localhost` (WSL2 không chuyển cổng socket qua 127.0.0.1, realtime.md §6).
 * Kết nối lỗi -> chỉ còn poll, các màn vẫn đúng. `onStatus(true|false)` báo trạng thái kết nối (để giãn / dồn nhịp poll).
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
export function useRealtimeEvent(
	event: string,
	onEvent: (data: unknown) => void,
	enabled = true,
	onStatus?: (connected: boolean) => void
) {
	const handler = useRef(onEvent);
	handler.current = onEvent;
	const status = useRef(onStatus);
	status.current = onStatus;

	useEffect(() => {
		if (!enabled) return;
		const url = socketUrl(realtimeConfig());
		if (!url) {
			status.current?.(false);
			return;
		}
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
			socket.on("connect", () => {
				status.current?.(true);
				handler.current(null);
			});
			socket.on("disconnect", () => status.current?.(false));
			socket.on("connect_error", () => status.current?.(false));
		} catch {
			socket = null;
		}
		return () => {
			socket?.off(event);
			socket?.disconnect();
			status.current?.(false);
		};
	}, [event, enabled]);
}
