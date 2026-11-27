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
	setEnabled: (enabled: boolean) => void;
	/** Gọi lại ngay (sau khi chuyển trạng thái pha chế). Trả danh sách mã đơn mới xuất hiện (trừ `quiet`). */
	refresh: (quiet?: string[]) => Promise<string[]>;
	/** Bỏ ngay các đơn khỏi hàng chờ (vd. vừa "Đã hoàn thành" trên máy này) — chấm đỏ giảm ngay, không thêm request. */
	dropItems: (names: string[]) => void;
	/**
	 * Không báo toast hàng chờ cho các đơn này (máy này vừa bấm "Đã làm", màn Pha chế đã có toast xác nhận).
	 * Gọi TRƯỚC khi gửi API: sự kiện realtime có thể tới trước khi API trả về (2026-11-27, nguyên nhân toast trùng / đè).
	 */
	mute: (names: string[]) => void;
	unmute: (names: string[]) => void;
};

let inflight: Promise<string[]> | null = null;
/** Đơn đang tắt tiếng -> hạn (ms). Hết hạn hoặc đã vào hàng chờ thì bỏ. */
const muted = new Map<string, number>();
const MUTE_MS = 60000;

function isMuted(name: string): boolean {
	const until = muted.get(name);
	if (until === undefined) return false;
	if (until < Date.now()) {
		muted.delete(name);
		return false;
	}
	return true;
}

export const useServeQueue = create<ServeQueueState>((set, get) => ({
	enabled: false,
	items: [],
	loadedAt: 0,
	primed: false,
	setEnabled: (enabled) => set(enabled ? { enabled } : { enabled, items: [], primed: false }),
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
					? rows.filter((o) => !seen.has(o.name) && !quiet.includes(o.name) && !isMuted(o.name)).map((o) => o.name)
					: [];
				// Đơn đã có trong hàng chờ thì không bao giờ "mới" lại -> bỏ khỏi danh sách tắt tiếng.
				for (const o of rows) muted.delete(o.name);
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
	mute: (names) => {
		const until = Date.now() + MUTE_MS;
		for (const n of names) muted.set(n, until);
	},
	unmute: (names) => {
		for (const n of names) muted.delete(n);
	},
}));
