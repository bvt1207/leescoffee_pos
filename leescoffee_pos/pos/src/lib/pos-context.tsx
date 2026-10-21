import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api } from "./api";
import type { MenuGroup, PosConfig } from "../types";

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
