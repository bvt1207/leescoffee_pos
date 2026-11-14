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
