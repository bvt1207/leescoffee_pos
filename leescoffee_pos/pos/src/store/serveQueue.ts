import { create } from "zustand";
import { api } from "../lib/api";
import type { ServeQueueItem } from "../types";

/**
 * Hàng chờ phục vụ của thu ngân (2026-11-23): đơn tại quầy đã "Đã làm", chờ mang tới thẻ bàn (Dine In)
 * hoặc gọi khách lấy (Take Away). Một nguồn cho chấm đỏ ở menu "Đơn hàng", toast + bíp, tab "Chờ phục vụ" ở Orders.
 * Poll do `lib/serve.ts::useServeQueuePoller` (gắn một lần ở App) — chỉ máy có quyền Orders (CASHIER / MANAGER).
 */
type ServeQueueState = {
	/** Poller đang chạy (role có quyền Orders). Role khác: refresh() không gọi API. */
	enabled: boolean;
	items: ServeQueueItem[];
	/** Date.now() lúc nhận dữ liệu — cộng vào waiting_seconds để đếm thời gian chờ. */
	loadedAt: number;
	/** Lần tải đầu đã xong (không báo toast cho các đơn có sẵn khi mở trang). */
	primed: boolean;
	/** Toast đơn mới (null = ẩn). */
	toast: string | null;
	/** Bấm toast -> Orders mở tab "Chờ phục vụ". */
	focusServe: boolean;
	setEnabled: (enabled: boolean) => void;
	/** Gọi lại ngay (sau khi chuyển trạng thái pha chế). Trả danh sách mã đơn mới xuất hiện. */
	refresh: () => Promise<string[]>;
	setToast: (toast: string | null) => void;
	setFocusServe: (focus: boolean) => void;
};

let inflight: Promise<string[]> | null = null;

export const useServeQueue = create<ServeQueueState>((set, get) => ({
	enabled: false,
	items: [],
	loadedAt: 0,
	primed: false,
	toast: null,
	focusServe: false,
	setEnabled: (enabled) => set(enabled ? { enabled } : { enabled, items: [], primed: false, toast: null }),
	refresh: () => {
		if (!get().enabled) return Promise.resolve([]);
		// Không chồng request: lần gọi trùng dùng chung kết quả lần đang chạy.
		if (inflight) return inflight;
		inflight = (async () => {
			try {
				const rows = (await api.getServeQueue()) || [];
				const { items: before, primed, enabled } = get();
				if (!enabled) return [];
				const seen = new Set(before.map((o) => o.name));
				const fresh = primed ? rows.filter((o) => !seen.has(o.name)).map((o) => o.name) : [];
				set({ items: rows, loadedAt: Date.now(), primed: true });
				return fresh;
			} finally {
				inflight = null;
			}
		})();
		return inflight;
	},
	setToast: (toast) => set({ toast }),
	setFocusServe: (focusServe) => set({ focusServe }),
}));
