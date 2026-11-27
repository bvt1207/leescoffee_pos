import { create } from "zustand";
import type { OrdersScope } from "../types";

/** Khoảng ngày của chế độ Lịch sử: hôm qua, 7 ngày gần nhất (gồm hôm nay), hoặc một ngày tự chọn. */
export type HistoryPreset = "yesterday" | "7d" | "day";

/** Bộ lọc màn Orders: nằm ngoài component nên giữ nguyên khi chuyển trang trong /pos (F5 thì về mặc định). */
type OrderFilterState = {
	mode: OrdersScope;
	preset: HistoryPreset;
	/** "YYYY-MM-DD" khi preset = "day". */
	day: string;
	setMode: (mode: OrdersScope) => void;
	setPreset: (preset: HistoryPreset) => void;
	setDay: (day: string) => void;
};

export const useOrderFilter = create<OrderFilterState>((set) => ({
	mode: "shift",
	preset: "yesterday",
	day: "",
	setMode: (mode) => set({ mode }),
	setPreset: (preset) => set({ preset }),
	setDay: (day) => set({ day, preset: "day" }),
}));
