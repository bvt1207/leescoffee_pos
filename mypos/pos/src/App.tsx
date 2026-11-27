import { Navigate, Outlet, useLocation } from "react-router-dom";
import AppHeader from "./components/AppHeader";
import ToastStack from "./components/ToastStack";
import { navOf, usePos } from "./lib/pos-context";
import { useChangeFeedPoller } from "./lib/changes";
import { useServeQueuePoller } from "./lib/serve";
import type { NavKey } from "./types";

// Đường dẫn (trong basename /pos) -> mục điều hướng cần quyền.
const PATH_NAV: { prefix: string; key: NavKey; exact?: boolean }[] = [
	{ prefix: "/", key: "sell", exact: true },
	{ prefix: "/orders", key: "orders" },
	{ prefix: "/kitchen", key: "kitchen" },
];

const NAV_PATH: Record<NavKey, string> = { sell: "/", orders: "/orders", kitchen: "/kitchen" };

function navOfPath(pathname: string): NavKey | null {
	const hit = PATH_NAV.find((p) => (p.exact ? pathname === p.prefix : pathname.startsWith(p.prefix)));
	return hit ? hit.key : null;
}

export default function App() {
	const { config, loading, error, reload } = usePos();
	const { pathname } = useLocation();

	const nav = navOf(config);
	const need = navOfPath(pathname);
	// Route guard (chỉ để gọn UI — backend vẫn chặn thật): mục không được phép -> mục đầu tiên được phép.
	const redirect = !loading && config && need && !nav.includes(need) && nav.length ? NAV_PATH[nav[0]] : null;
	const noRole = !loading && !!config && nav.length === 0;

	// Thông báo đơn "Đã làm" (2026-11-23): CHỈ user có role POS CASHIER poll + nhận toast / chấm đỏ (server lọc đúng
	// POS Profile). KITCHEN-only, MANAGER không có role CASHIER: không poll, không toast. User có cả CASHIER + role khác: vẫn nhận.
	useServeQueuePoller(!loading && !!config?.roles?.cashier && nav.includes("orders"));
	// Phiên bản thay đổi theo POS Profile (lib/changes.ts): chỉ poll khi có màn đăng ký (Pha chế, Orders, hàng chờ, chọn thẻ bàn).
	useChangeFeedPoller(!loading && !!config && nav.length > 0);

	return (
		<div className="pos-app">
			<AppHeader />

			<main className="pos-main">
				{error ? (
					<div className="pos-alert pos-alert--error">
						{error}
						<button type="button" className="pos-btn pos-btn--ghost" onClick={reload}>
							Thử lại
						</button>
					</div>
				) : null}

				{loading ? (
					<div className="pos-empty">Đang tải…</div>
				) : redirect ? (
					<Navigate to={redirect} replace />
				) : noRole ? (
					<div className="pos-alert pos-alert--error">
						Tài khoản chưa được gán role POS (POS MANAGER / POS CASHIER / POS KITCHEN). Liên hệ quản lý.
					</div>
				) : (
					<Outlet />
				)}
			</main>

			{/* Toast dùng chung mọi màn (hàng chờ thu ngân + xác nhận màn Pha chế): xếp cột, tối đa 3 (store/toasts.ts). */}
			<ToastStack />
		</div>
	);
}
