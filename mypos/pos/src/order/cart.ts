import { create } from "zustand";
import { normalizeOptions, optionsKey } from "../lib/options";
import type { CartOption, OptionGroup } from "../types";
import type { CartLine, MenuItem, SizeOption } from "./types";

/** Giỏ của khách (chỉ trong bộ nhớ tab). Cùng món khác tùy chọn = dòng khác (giống POS). */

const MAX_QTY = 20; // khớp customer_order_api.MAX_QTY_PER_LINE

interface CartState {
	lines: CartLine[];
	note: string;
	add: (item: MenuItem, size: SizeOption, options: CartOption[], qty: number) => void;
	setQty: (key: string, qty: number) => void;
	remove: (key: string) => void;
	setNote: (note: string) => void;
	clear: () => void;
}

export function lineKey(itemCode: string, options: CartOption[], groups: OptionGroup[]): string {
	return `${itemCode}|${optionsKey(normalizeOptions(options, groups))}`;
}

export const useOrderCart = create<CartState>((set) => ({
	lines: [],
	note: "",
	add: (item, size, options, qty) =>
		set((s) => {
			const opts = normalizeOptions(options, item.option_groups);
			const key = lineKey(size.item_code, opts, item.option_groups);
			const hit = s.lines.find((l) => l.key === key);
			if (hit) {
				return {
					lines: s.lines.map((l) => (l.key === key ? { ...l, qty: Math.min(MAX_QTY, l.qty + qty) } : l)),
				};
			}
			const line: CartLine = {
				key,
				item_name: item.name,
				size_label: size.label,
				item_code: size.item_code,
				rate: size.rate,
				qty: Math.min(MAX_QTY, qty),
				options: opts,
				option_groups: item.option_groups,
				image: item.image,
			};
			return { lines: [...s.lines, line] };
		}),
	setQty: (key, qty) =>
		set((s) => ({
			lines:
				qty <= 0
					? s.lines.filter((l) => l.key !== key)
					: s.lines.map((l) => (l.key === key ? { ...l, qty: Math.min(MAX_QTY, qty) } : l)),
		})),
	remove: (key) => set((s) => ({ lines: s.lines.filter((l) => l.key !== key) })),
	setNote: (note) => set({ note: note.slice(0, 200) }),
	clear: () => set({ lines: [], note: "" }),
}));

export const MAX_LINE_QTY = MAX_QTY;

/** Payload gửi server: chỉ item_code, qty, options (server tính lại mọi thứ). */
export function cartPayload(lines: CartLine[]) {
	return lines.map((l) => ({ item_code: l.item_code, qty: l.qty, options: l.options }));
}

// ---------------------------------------------------------------------------
// Lưu giỏ ở localStorage theo (mã QR + khách). Không lưu lên server.
// - Khôi phục sau F5 / đóng-mở tab / đăng nhập lại cùng thiết bị.
// - Xóa khi: Thoát chủ động (discardCart), tạo đơn thành công (clear -> giỏ rỗng -> xóa bản lưu),
//   bản lưu quá CART_TTL_MS kể từ lần sửa cuối.
// - Phiên hết hạn: chỉ tách khỏi bộ nhớ (attachCartStorage(null)), giữ bản lưu cho lần đăng nhập lại.
// ---------------------------------------------------------------------------

const CART_TTL_MS = 12 * 3600 * 1000;
const CART_VERSION = 1;

interface SavedCart {
	v: number;
	savedAt: number;
	lines: CartLine[];
	note: string;
}

let storageKey: string | null = null;
let restoring = false;

export const cartStorageKey = (qrToken: string, cartKey: string) => `mypos_order_cart:${qrToken}:${cartKey}`;

function readSaved(key: string): SavedCart | null {
	try {
		const raw = window.localStorage.getItem(key);
		if (!raw) return null;
		const saved = JSON.parse(raw) as SavedCart;
		if (saved.v !== CART_VERSION || !Array.isArray(saved.lines) || Date.now() - saved.savedAt > CART_TTL_MS) {
			window.localStorage.removeItem(key);
			return null;
		}
		return saved;
	} catch {
		return null;
	}
}

function removeSaved(key: string) {
	try {
		window.localStorage.removeItem(key);
	} catch {
		/* ignore */
	}
}

/** Gắn giỏ với một khóa lưu (null = tách: xóa giỏ trong bộ nhớ, KHÔNG xóa bản lưu). */
export function attachCartStorage(key: string | null) {
	if (key === storageKey) return;
	storageKey = key;
	restoring = true;
	try {
		if (!key) {
			useOrderCart.setState({ lines: [], note: "" });
			return;
		}
		const saved = readSaved(key);
		if (saved) {
			useOrderCart.setState({
				lines: saved.lines.map((l) => ({ ...l, qty: Math.min(MAX_QTY, Math.max(1, Math.floor(l.qty) || 1)) })),
				note: String(saved.note || "").slice(0, 200),
			});
		}
	} finally {
		restoring = false;
	}
	// Không có bản lưu nhưng giỏ đang có món (thêm trước khi biết khóa) -> lưu luôn.
	if (key && !readSaved(key)) persist(useOrderCart.getState());
}

/** Thoát chủ động: xóa bản lưu + giỏ trong bộ nhớ. */
export function discardCart() {
	if (storageKey) removeSaved(storageKey);
	storageKey = null;
	useOrderCart.setState({ lines: [], note: "" });
}

/** Bỏ dòng có món không còn trong menu hiện tại (menu đổi giữa hai lần vào). */
export function pruneCart(validItemCodes: Set<string>) {
	const { lines } = useOrderCart.getState();
	const kept = lines.filter((l) => validItemCodes.has(l.item_code));
	if (kept.length !== lines.length) useOrderCart.setState({ lines: kept });
}

function persist(state: { lines: CartLine[]; note: string }) {
	if (!storageKey || restoring) return;
	if (!state.lines.length && !state.note) {
		removeSaved(storageKey);
		return;
	}
	try {
		const saved: SavedCart = { v: CART_VERSION, savedAt: Date.now(), lines: state.lines, note: state.note };
		window.localStorage.setItem(storageKey, JSON.stringify(saved));
	} catch {
		/* chế độ riêng tư / hết bộ nhớ: giỏ chỉ còn trong tab */
	}
}

useOrderCart.subscribe((state, prev) => {
	if (state.lines !== prev.lines || state.note !== prev.note) persist(state);
});
