import { create } from "zustand";
import { api } from "../lib/api";
import type { ServeQueueItem } from "../types";

/**
 * Hàng chờ phục vụ của thu ngân (2026-11-23): đơn tại quầy đã "Đã làm", chờ mang tới thẻ bàn (Dine In)
 * hoặc gọi khách lấy (Take Away). Một nguồn cho chấm đỏ ở menu "Pha chế" + toast + bíp. Kết thúc đơn = nút
 * "Đã hoàn thành" ở màn Pha chế (tab Đã làm); thẻ bàn tự nhả. Không có bước "đã phục vụ" riêng (2026-11-23).
 * Poll do `lib/serve.ts::useServeQueuePoller` (gắn một lần ở App) — chỉ user có role POS CASHIER (2026-11-23).
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
	setEnabled: (enabled: boolean) => void;
	/** Gọi lại ngay (sau khi chuyển trạng thái pha chế). Trả danh sách mã đơn mới xuất hiện (trừ `quiet`). */
	refresh: (quiet?: string[]) => Promise<string[]>;
	/** Bỏ ngay các đơn khỏi hàng chờ (vd. vừa "Đã hoàn thành" trên máy này) — chấm đỏ giảm ngay, không thêm request. */
	dropItems: (names: string[]) => void;
	setToast: (toast: string | null) => void;
};

let inflight: Promise<string[]> | null = null;

export const useServeQueue = create<ServeQueueState>((set, get) => ({
	enabled: false,
	items: [],
	loadedAt: 0,
	primed: false,
	toast: null,
	setEnabled: (enabled) => set(enabled ? { enabled } : { enabled, items: [], primed: false, toast: null }),
	refresh: (quiet = []) => {
		if (!get().enabled) return Promise.resolve([]);
		// Không chồng request: lần gọi trùng dùng chung kết quả lần đang chạy.
		if (inflight) return inflight;
		inflight = (async () => {
			try {
				const rows = (await api.getServeQueue()) || [];
				const { items: before, primed, enabled } = get();
				if (!enabled) return [];
				const seen = new Set(before.map((o) => o.name));
				const fresh = primed
					? rows.filter((o) => !seen.has(o.name) && !quiet.includes(o.name)).map((o) => o.name)
					: [];
				set({ items: rows, loadedAt: Date.now(), primed: true });
				return fresh;
			} finally {
				inflight = null;
			}
		})();
		return inflight;
	},
	dropItems: (names) => {
		if (!names.length) return;
		set({ items: get().items.filter((o) => !names.includes(o.name)) });
	},
	setToast: (toast) => set({ toast }),
}));
