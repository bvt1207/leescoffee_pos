import { create } from "zustand";
import type { CartLine } from "../types";

interface CartState {
	lines: CartLine[];
	add: (item: CartLine) => void;
	increment: (item_code: string) => void;
	decrement: (item_code: string) => void;
	remove: (item_code: string) => void;
	clear: () => void;
}

export const useCart = create<CartState>((set) => ({
	lines: [],

	add: (item) =>
		set((state) => {
			const existing = state.lines.find((line) => line.item_code === item.item_code);
			if (existing) {
				return {
					lines: state.lines.map((line) =>
						line.item_code === item.item_code
							? { ...line, qty: line.qty + (item.qty || 1) }
							: line
					),
				};
			}
			return { lines: [...state.lines, { ...item, qty: item.qty || 1 }] };
		}),

	increment: (item_code) =>
		set((state) => ({
			lines: state.lines.map((line) =>
				line.item_code === item_code ? { ...line, qty: line.qty + 1 } : line
			),
		})),

	decrement: (item_code) =>
		set((state) => ({
			lines: state.lines
				.map((line) =>
					line.item_code === item_code ? { ...line, qty: line.qty - 1 } : line
				)
				.filter((line) => line.qty > 0),
		})),

	remove: (item_code) =>
		set((state) => ({
			lines: state.lines.filter((line) => line.item_code !== item_code),
		})),

	clear: () => set({ lines: [] }),
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
