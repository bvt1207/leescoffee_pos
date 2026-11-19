import { create } from "zustand";

/** Tab nhóm món đang chọn ở lưới món: nằm ngoài component nên giữ nguyên khi chuyển trang trong /pos. */
type MenuFilterState = {
	group: string;
	setGroup: (value: string) => void;
};

export const ALL_GROUPS = "all";
/** Khóa tab cho món không có Item Group (nhãn hiển thị "Khác"). */
export const NO_GROUP = "__none__";

export const useMenuFilter = create<MenuFilterState>((set) => ({
	group: ALL_GROUPS,
	setGroup: (value) => set({ group: value }),
}));
