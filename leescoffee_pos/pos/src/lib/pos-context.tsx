import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api } from "./api";
import type { KitchenStep, KitchenTransition, MenuGroup, NavKey, PosConfig } from "../types";

const ALL_NAV: NavKey[] = ["sell", "orders", "kitchen"];
const ALL_STEPS: KitchenStep[] = ["Chưa làm", "Đã làm", "Đã hoàn thành"];

/** Mục điều hướng được phép (backend cũ không trả `nav` -> hiện đủ như trước). */
export function navOf(config: PosConfig | null): NavKey[] {
	return config?.nav ?? ALL_NAV;
}

/** Tab pha chế được xem. */
export function kitchenTabsOf(config: PosConfig | null): KitchenStep[] {
	return config?.kitchen_tabs ?? ALL_STEPS;
}

/** Bước chuyển được phép. */
export function kitchenTransitionsOf(config: PosConfig | null): KitchenTransition[] {
	return (
		config?.kitchen_transitions ?? [
			{ from: "Chưa làm", to: "Đã làm" },
			{ from: "Đã làm", to: "Đã hoàn thành" },
		]
	);
}

interface PosContextValue {
	config: PosConfig | null;
	menus: MenuGroup[];
	loading: boolean;
	error: string;
	reload: () => Promise<void>;
}

const PosContext = createContext<PosContextValue>({
	config: null,
	menus: [],
	loading: true,
	error: "",
	reload: async () => {},
});

export function PosProvider({ children }: { children: ReactNode }) {
	const [config, setConfig] = useState<PosConfig | null>(null);
	const [menus, setMenus] = useState<MenuGroup[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");

	const reload = useCallback(async () => {
		setLoading(true);
		setError("");
		try {
			const [cfg, menuRows] = await Promise.all([api.getPosConfig(), api.getMenuItems()]);
			setConfig(cfg);
			setMenus(Array.isArray(menuRows) ? (menuRows as MenuGroup[]) : []);
			if (cfg?.brand?.name) {
				document.title = `${cfg.brand.name} — POS`;
			}
		} catch (err) {
			setError(err instanceof Error ? err.message : String(err));
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		reload();
	}, [reload]);

	const value = useMemo(
		() => ({ config, menus, loading, error, reload }),
		[config, menus, loading, error, reload]
	);

	return <PosContext.Provider value={value}>{children}</PosContext.Provider>;
}

export function usePos(): PosContextValue {
	return useContext(PosContext);
}
