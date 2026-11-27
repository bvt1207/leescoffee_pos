import { create } from "zustand";

/**
 * Toast dùng chung cho mọi màn trong App (Bán món / Đơn hàng / Pha chế) — 2026-11-27.
 * Trước đây có 2 nguồn toast riêng (màn Pha chế + hàng chờ thu ngân) cùng vị trí cố định -> đè lên nhau.
 * Giờ: MỘT danh sách, hiển thị thành cột (components/ToastStack.tsx), tối đa MAX_TOASTS (cũ nhất tự tắt trước),
 * cùng `key` -> thay nội dung, không thêm toast thứ hai (một sự kiện chỉ một toast).
 */
export const MAX_TOASTS = 3;

export interface ToastItem {
	id: number;
	text: string;
	key?: string;
	/** Bấm để tắt (toast xác nhận của màn Pha chế); toast hàng chờ chỉ hiển thị. */
	dismissible: boolean;
}

type ToastState = {
	toasts: ToastItem[];
	push: (text: string, opts?: { key?: string; ms?: number; dismissible?: boolean }) => void;
	dismiss: (id: number) => void;
};

let seq = 0;
const timers = new Map<number, number>();

function clearTimer(id: number) {
	window.clearTimeout(timers.get(id));
	timers.delete(id);
}

export const useToasts = create<ToastState>((set, get) => ({
	toasts: [],
	push: (text, { key, ms = 5000, dismissible = false } = {}) => {
		if (!text) return;
		const current = get().toasts;
		const same = key ? current.find((t) => t.key === key) : undefined;
		let id: number;
		let next: ToastItem[];
		if (same) {
			id = same.id;
			clearTimer(id);
			next = current.map((t) => (t.id === id ? { ...t, text, dismissible } : t));
		} else {
			id = ++seq;
			next = [...current, { id, text, key, dismissible }];
			while (next.length > MAX_TOASTS) {
				clearTimer(next[0].id);
				next = next.slice(1);
			}
		}
		set({ toasts: next });
		timers.set(id, window.setTimeout(() => get().dismiss(id), ms));
	},
	dismiss: (id) => {
		clearTimer(id);
		set({ toasts: get().toasts.filter((t) => t.id !== id) });
	},
}));

/** Gọi từ ngoài component (lib/serve.ts, Kitchen.tsx). */
export const pushToast: ToastState["push"] = (text, opts) => useToasts.getState().push(text, opts);
