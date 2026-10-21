import { Outlet } from "react-router-dom";
import AppHeader from "./components/AppHeader";
import { usePos } from "./lib/pos-context";

export default function App() {
	const { loading, error, reload } = usePos();

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

				{loading ? <div className="pos-empty">Đang tải…</div> : <Outlet />}
			</main>
		</div>
	);
}
