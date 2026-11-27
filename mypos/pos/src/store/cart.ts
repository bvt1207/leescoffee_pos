import { create } from "zustand";
import { normalizeOptions, optionsKey } from "../lib/options";
import type { CartLine, CartOption } from "../types";

type NewLine = Omit<CartLine, "qty" | "options" | "option_groups"> &
	Partial<Pick<CartLine, "options" | "option_groups">> & { qty?: number };

interface CartState {
	lines: CartLine[];
	add: (item: NewLine) => void;
	addVariant: (line: NewLine) => void;
	increment: (key: string) => void;
	decrement: (key: string) => void;
	/** Đặt số lượng dòng (số nguyên, kẹp 1..MAX_LINE_QTY); không xóa dòng. */
	setQty: (key: string, qty: number) => void;
	remove: (key: string) => void;
	removeLine: (key: string) => void;
	/** Đổi tùy chọn của dòng; trả khóa mới (trùng dòng khác thì gộp qty). */
	setLineOptions: (key: string, options: CartOption[]) => string;
	setNote: (key: string, note: string) => void;
	setOrderNote: (note: string) => void;
	clear: () => void;
	orderNote: string;
	// Số điểm Loyalty khách muốn đổi cho đơn đang tạo (0 = không đổi).
	redeemPoints: number;
	setRedeemPoints: (points: number) => void;
}

/** Số lượng tối đa mỗi dòng khi gõ trực tiếp trong giỏ. */
export const MAX_LINE_QTY = 999;

// Dòng giỏ phân biệt theo item_code (variant đã gồm size) + tổ hợp tùy chọn đã chuẩn hóa:
// cùng món khác tùy chọn là dòng khác nhau. key = `${item_code}|${group=value;...}`.
export function cartLineKey(line: Pick<CartLine, "item_code" | "options">): string {
	return `${line.item_code}|${optionsKey(line.options || [])}`;
}

function toLine(item: NewLine): CartLine {
	const groups = item.option_groups || [];
	return {
		...item,
		option_groups: groups,
		options: normalizeOptions(item.options || [], groups),
		qty: item.qty || 1,
	} as CartLine;
}

function addLine(lines: CartLine[], item: NewLine): CartLine[] {
	const line = toLine(item);
	const key = cartLineKey(line);
	if (lines.some((l) => cartLineKey(l) === key)) {
		return lines.map((l) => (cartLineKey(l) === key ? { ...l, qty: l.qty + line.qty } : l));
	}
	return [...lines, line];
}

export const useCart = create<CartState>((set, get) => ({
	lines: [],
	orderNote: "",
	redeemPoints: 0,

	add: (item) => set((state) => ({ lines: addLine(state.lines, item) })),

	// Thêm dòng đã chọn size (variant).
	addVariant: (line) => set((state) => ({ lines: addLine(state.lines, line) })),

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

	setQty: (key, qty) => {
		const value = Math.min(MAX_LINE_QTY, Math.max(1, Math.floor(qty)));
		if (!Number.isFinite(value)) return;
		set((state) => ({
			lines: state.lines.map((line) => (cartLineKey(line) === key ? { ...line, qty: value } : line)),
		}));
	},

	remove: (key) =>
		set((state) => ({
			lines: state.lines.filter((line) => cartLineKey(line) !== key),
		})),

	removeLine: (key) =>
		set((state) => ({
			lines: state.lines.filter((line) => cartLineKey(line) !== key),
		})),

	setLineOptions: (key, options) => {
		const line = get().lines.find((l) => cartLineKey(l) === key);
		if (!line) return key;
		const normalized = normalizeOptions(options, line.option_groups);
		const newKey = cartLineKey({ item_code: line.item_code, options: normalized });
		if (newKey === key) return key;
		set((state) => {
			if (state.lines.some((l) => cartLineKey(l) === newKey)) {
				// Gộp vào dòng đã có cùng tổ hợp: tăng qty dòng kia, bỏ dòng này.
				return {
					lines: state.lines
						.filter((l) => cartLineKey(l) !== key)
						.map((l) => (cartLineKey(l) === newKey ? { ...l, qty: l.qty + line.qty } : l)),
				};
			}
			return {
				lines: state.lines.map((l) => (cartLineKey(l) === key ? { ...l, options: normalized } : l)),
			};
		});
		return newKey;
	},

	setNote: (key, note) =>
		set((state) => ({
			lines: state.lines.map((line) =>
				cartLineKey(line) === key ? { ...line, note } : line
			),
		})),

	setOrderNote: (note) => set({ orderNote: note }),

	setRedeemPoints: (points) => set({ redeemPoints: Math.max(0, Math.floor(points || 0)) }),

	clear: () => set({ lines: [], orderNote: "", redeemPoints: 0 }),
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
