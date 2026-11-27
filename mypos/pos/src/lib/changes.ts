import { useCallback, useEffect, useRef } from "react";
import { create } from "zustand";
import { usePolling } from "../order/poll";
import { api } from "./api";
import { useRealtimeEvent } from "./realtime";

/**
 * Tải lại theo phiên bản thay đổi của POS Profile (2026-11-25, `docs/rules/realtime.md`).
 *
 * - MỘT poller ở App gọi `get_pos_changes` (server chỉ đọc Redis). Chu kỳ = nhỏ nhất trong các màn đang đăng ký
 *   (Pha chế / Orders / chọn thẻ bàn: CHANGE_POLL_MS; chỉ hàng chờ thu ngân: SERVE_POLL_MS). Không màn nào đăng ký -> không poll.
 * - Mỗi màn dùng `usePosRefresh(load)`: tải khi mở, khi phiên bản đổi, và lưới an toàn định kỳ (dữ liệu đổi không qua hook).
 * - Tab ẩn -> dừng; hiện lại -> hỏi phiên bản ngay. Lỗi mạng -> giãn nhịp (usePolling), lưới an toàn vẫn chạy.
 * - Giai đoạn 3 (2026-11-25): server đẩy `mypos_pos_changed` {p, v} (phòng "all") sau mỗi lần tăng phiên bản. Socket đang kết nối
 *   -> nhận phiên bản ngay, poll giãn ra REALTIME_POLL_MS (lưới an toàn); mất kết nối -> về chu kỳ thường (4 giây); kết nối lại -> hỏi ngay.
 */

/** Chu kỳ poll phiên bản khi không có socket (quyết định D3): đơn mới hiện trong ≤ 5 giây. */
export const CHANGE_POLL_MS = 4000;
/** Lưới an toàn mặc định: tải đầy đủ dù phiên bản không đổi. */
export const SAFETY_REFRESH_MS = 60000;
/** Chu kỳ poll phiên bản khi socket đang kết nối (sự kiện realtime là đường chính). */
export const REALTIME_POLL_MS = 30000;
/** Sự kiện realtime phiên bản thay đổi (change_feed.REALTIME_EVENT); màn /pos/status dùng lại. */
export const REALTIME_EVENT = "mypos_pos_changed";

type ChangeState = {
	/** "<profile>|<phiên bản>" lần đọc gần nhất (null = chưa đọc). */
	v: string | null;
	/** POS Profile của user (từ get_pos_changes) — lọc sự kiện realtime. */
	profile: string | null;
	/** Socket realtime đang kết nối. */
	connected: boolean;
	/** Chu kỳ mong muốn của từng màn đang đăng ký. */
	intervals: Record<string, number>;
	setV: (v: string) => void;
	setProfile: (profile: string) => void;
	setConnected: (connected: boolean) => void;
	register: (id: string, ms: number) => void;
	unregister: (id: string) => void;
};

export const useChanges = create<ChangeState>((set, get) => ({
	v: null,
	profile: null,
	connected: false,
	intervals: {},
	setV: (v) => {
		if (get().v !== v) set({ v });
	},
	setProfile: (profile) => {
		if (get().profile !== profile) set({ profile });
	},
	setConnected: (connected) => {
		if (get().connected !== connected) set({ connected });
	},
	register: (id, ms) => set({ intervals: { ...get().intervals, [id]: ms } }),
	unregister: (id) => {
		const next = { ...get().intervals };
		delete next[id];
		set({ intervals: next });
	},
}));

/** Gắn MỘT lần ở App (sau khi có cấu hình). */
export function useChangeFeedPoller(enabled: boolean): void {
	const intervals = useChanges((s) => s.intervals);
	const connected = useChanges((s) => s.connected);
	const values = Object.values(intervals);
	const base = values.length ? Math.min(...values) : 0;
	const active = enabled && base > 0;
	// Socket kết nối -> poll chỉ là lưới an toàn. Đổi chu kỳ khởi động lại vòng poll và hỏi ngay (kết nối / mất kết nối).
	const interval = connected ? Math.max(base, REALTIME_POLL_MS) : base;
	usePolling(
		async (signal) => {
			const r = await api.getPosChanges(signal);
			const st = useChanges.getState();
			st.setProfile(r.profile);
			st.setV(`${r.profile}|${r.v}`);
		},
		active,
		interval || CHANGE_POLL_MS
	);
	useRealtimeEvent(
		REALTIME_EVENT,
		(data) => {
			const msg = data as { p?: string; v?: string } | null;
			const st = useChanges.getState();
			// Payload chỉ {p, v}: bỏ qua sự kiện của POS Profile khác (phòng "all", quyết định D2-i).
			if (!msg || !msg.p || msg.v == null || msg.p !== st.profile) return;
			st.setV(`${msg.p}|${msg.v}`);
		},
		active,
		(ok) => useChanges.getState().setConnected(ok)
	);
}

let seq = 0;

/**
 * Chạy `load` khi mở màn, khi phiên bản đổi và mỗi `safetyMs`. Không chồng: đang chạy mà có yêu cầu mới -> chạy thêm
 * đúng một lần sau khi xong. Đổi `key` (vd. đơn đang chọn) -> tải lại ngay. `load` đọc qua ref.
 */
export function usePosRefresh(
	load: () => Promise<unknown>,
	{
		enabled = true,
		intervalMs = CHANGE_POLL_MS,
		safetyMs = SAFETY_REFRESH_MS,
		key = "",
	}: { enabled?: boolean; intervalMs?: number; safetyMs?: number; key?: string } = {}
): void {
	const loadRef = useRef(load);
	loadRef.current = load;
	const state = useRef({ running: false, again: false });

	const run = useCallback(async () => {
		const st = state.current;
		if (st.running) {
			st.again = true;
			return;
		}
		st.running = true;
		try {
			do {
				st.again = false;
				await loadRef.current().catch(() => undefined);
			} while (st.again);
		} finally {
			st.running = false;
		}
	}, []);

	useEffect(() => {
		if (!enabled) return;
		const id = `c${++seq}`;
		const store = useChanges.getState();
		store.register(id, intervalMs);
		let seen = store.v;
		void run();
		const unsubscribe = useChanges.subscribe((s) => {
			if (s.v !== null && s.v !== seen) {
				seen = s.v;
				void run();
			}
		});
		return () => {
			unsubscribe();
			useChanges.getState().unregister(id);
		};
	}, [enabled, intervalMs, key, run]);

	usePolling(() => run(), enabled && safetyMs > 0, safetyMs || SAFETY_REFRESH_MS, { immediate: false });
}
