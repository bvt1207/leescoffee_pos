import { create } from "zustand";
import type { CartLine } from "../types";

const ICE_SUGAR = [50, 70, 100] as const;

interface CartState {
	lines: CartLine[];
	add: (item: CartLine) => void;
	addVariant: (line: Omit<CartLine, "qty"> & { qty?: number }) => void;
	increment: (key: string) => void;
	decrement: (key: string) => void;
	remove: (key: string) => void;
	removeLine: (key: string) => void;
	changeIceSugar: (key: string, ice: number, sugar: number) => void;
	setNote: (key: string, note: string) => void;
	setOrderNote: (note: string) => void;
	clear: () => void;
	orderNote: string;
}

// Dòng giỏ phân biệt theo item_code + ice + sugar (cùng món khác đường/đá
// là dòng khác nhau). key = `${item_code}|${ice}|${sugar}`.
export function cartLineKey(line: CartLine): string {
	return `${line.item_code}|${line.ice ?? 100}|${line.sugar ?? 100}`;
}

export const useCart = create<CartState>((set, get) => ({
	lines: [],
	orderNote: "",

	add: (item) =>
		set((state) => {
			const key = cartLineKey(item);
			const existing = state.lines.find((line) => cartLineKey(line) === key);
			if (existing) {
				return {
					lines: state.lines.map((line) =>
						cartLineKey(line) === key
							? { ...line, qty: line.qty + (item.qty || 1) }
							: line
					),
				};
			}
			return {
				lines: [
					...state.lines,
					{
						...item,
						ice: item.ice ?? 100,
						sugar: item.sugar ?? 100,
						qty: item.qty || 1,
					},
				],
			};
		}),

	// Thêm dòng đã chọn size (variant) — phân biệt theo item_code + ice + sugar.
	addVariant: (line) =>
		set((state) => {
			const key = cartLineKey(line as CartLine);
			const existing = state.lines.find((l) => cartLineKey(l) === key);
			if (existing) {
				return {
					lines: state.lines.map((l) =>
						cartLineKey(l) === key
							? { ...l, qty: l.qty + (line.qty || 1) }
							: l
					),
				};
			}
			return {
				lines: [
					...state.lines,
					{
						...line,
						ice: line.ice ?? 100,
						sugar: line.sugar ?? 100,
						qty: line.qty || 1,
					} as CartLine,
				],
			};
		}),

	increment: (key) =>
		set((state) => ({
			lines: state.lines.map((line) =>
				cartLineKey(line) === key ? { ...line, qty: line.qty + 1 } : line
			),
		})),

	decrement: (key) =>
		set((state) => ({
			lines: state.lines
				.map((line) =>
					cartLineKey(line) === key ? { ...line, qty: line.qty - 1 } : line
				)
				.filter((line) => line.qty > 0),
		})),

	remove: (key) =>
		set((state) => ({
			lines: state.lines.filter((line) => cartLineKey(line) !== key),
		})),

	removeLine: (key) =>
		set((state) => ({
			lines: state.lines.filter((line) => cartLineKey(line) !== key),
		})),

	changeIceSugar: (key, ice, sugar) =>
		set((state) => {
			// Thay thế dòng cũ bằng dòng mới (đổi key) nếu ice/sugar thay đổi.
			const line = state.lines.find((l) => cartLineKey(l) === key);
			if (!line) return { lines: state.lines };
			const newKey = cartLineKey({ ...line, ice, sugar });
			const exists = state.lines.some((l) => cartLineKey(l) === newKey);
			if (exists) {
				// Gộp vào dòng đã có: tăng qty dòng kia, xóa dòng này.
				return {
					lines: state.lines
						.filter((l) => cartLineKey(l) !== key)
						.map((l) =>
							cartLineKey(l) === newKey ? { ...l, qty: l.qty + line.qty } : l
						),
				};
			}
			return {
				lines: state.lines.map((l) =>
					cartLineKey(l) === key ? { ...l, ice, sugar } : l
				),
			};
		}),

	setNote: (key, note) =>
		set((state) => ({
			lines: state.lines.map((line) =>
				cartLineKey(line) === key ? { ...line, note } : line
			),
		})),

	setOrderNote: (note) => set({ orderNote: note }),

	clear: () => set({ lines: [], orderNote: "" }),
}));

export function cartTotal(lines: CartLine[]): number {
	return lines.reduce((sum, line) => sum + line.price * line.qty, 0);
}

export function cartCount(lines: CartLine[]): number {
	return lines.reduce((sum, line) => sum + line.qty, 0);
}

export function formatMoney(amount: number, currency = "VND"): string {
	const value = Math.round(amount || 0);
	const formatted = value.toLocaleString("vi-VN");
	return currency ? `${formatted} ${currency}` : formatted;
}
