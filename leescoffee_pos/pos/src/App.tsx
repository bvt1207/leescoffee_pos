import { useEffect } from "react";
import { Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import AppHeader from "./components/AppHeader";
import { navOf, usePos } from "./lib/pos-context";
import { useServeQueuePoller } from "./lib/serve";
import { useServeQueue } from "./store/serveQueue";
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

	// Hàng chờ phục vụ (2026-11-23): chỉ máy có quyền Orders (CASHIER / MANAGER) poll; KITCHEN không thêm request.
	useServeQueuePoller(!loading && !!config && nav.includes("orders"));
	const toast = useServeQueue((s) => s.toast);
	const setToast = useServeQueue((s) => s.setToast);
	const setFocusServe = useServeQueue((s) => s.setFocusServe);
	const navigate = useNavigate();

	// Toast tự tắt sau 8 giây; thông báo bền là chấm đỏ ở "Đơn hàng" + tab "Chờ phục vụ".
	useEffect(() => {
		if (!toast) return;
		const t = window.setTimeout(() => setToast(null), 8000);
		return () => window.clearTimeout(t);
	}, [toast, setToast]);

	const openServe = () => {
		setToast(null);
		setFocusServe(true);
		navigate("/orders");
	};

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

			{toast ? (
				<button type="button" className="pos-toast pos-toast--serve" role="status" onClick={openServe}>
					{toast}
					<span className="pos-toast__hint">Bấm để xem</span>
				</button>
			) : null}
		</div>
	);
}
