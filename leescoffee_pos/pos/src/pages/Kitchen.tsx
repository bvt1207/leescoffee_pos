import { useCallback, useEffect, useMemo, useState } from "react";
import ReceiptModal from "../components/ReceiptModal";
import { api } from "../lib/api";
import type { KitchenOrder, OrderDetail } from "../types";

const STEPS = ["Chưa làm", "Đã làm", "Đã hoàn thành"] as const;
type Step = (typeof STEPS)[number];

const NEXT: Record<string, { to: Step; label: string } | undefined> = {
	"Chưa làm": { to: "Đã làm", label: "Đã làm" },
	"Đã làm": { to: "Đã hoàn thành", label: "Đã hoàn thành" },
};

const typeLabel = (t: string) => (t === "Take Away" ? "Mang đi" : "Tại quán");

function parseTime(s: string): number {
	return new Date(s.replace(" ", "T")).getTime();
}

function waitInfo(creation: string, now: number) {
	const min = Math.max(0, Math.floor((now - parseTime(creation)) / 60000));
	const level = min >= 10 ? "late" : min >= 5 ? "warn" : "ok";
	return { min, level };
}

export default function Kitchen() {
	const [orders, setOrders] = useState<KitchenOrder[]>([]);
	const [tab, setTab] = useState<Step>("Chưa làm");
	const [busy, setBusy] = useState<string | null>(null);
	const [error, setError] = useState("");
	const [loading, setLoading] = useState(true);
	const [now, setNow] = useState(Date.now());
	const [toast, setToast] = useState<string | null>(null);
	const [ticket, setTicket] = useState<OrderDetail | null>(null);
	const [printBusy, setPrintBusy] = useState<string | null>(null);

	const load = useCallback(async () => {
		try {
			setOrders((await api.getKitchenOrders()) || []);
			setError("");
		} catch (err) {
			setError(err instanceof Error ? err.message : String(err));
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		load();
		const t = window.setInterval(load, 5000);
		const c = window.setInterval(() => setNow(Date.now()), 30000);
		return () => {
			window.clearInterval(t);
			window.clearInterval(c);
		};
	}, [load]);

	// Toast tự tắt sau 5 giây
	useEffect(() => {
		if (!toast) return;
		const t = window.setTimeout(() => setToast(null), 5000);
		return () => window.clearTimeout(t);
	}, [toast]);

	const localToday = new Date(Date.now() - new Date().getTimezoneOffset() * 60000)
		.toISOString()
		.slice(0, 10);

	const counts = useMemo(() => {
		const c: Record<string, number> = { "Chưa làm": 0, "Đã làm": 0, "Đã hoàn thành": 0 };
		orders.forEach((o) => {
			if (o.kitchen_status === "Đã hoàn thành" && !o.creation.startsWith(localToday)) return;
			c[o.kitchen_status] = (c[o.kitchen_status] || 0) + 1;
		});
		return c;
	}, [orders, localToday]);

	const list = useMemo(
		() =>
			orders.filter(
				(o) =>
					o.kitchen_status === tab &&
					(tab !== "Đã hoàn thành" || o.creation.startsWith(localToday))
			),
		[orders, tab, localToday]
	);

	const advance = async (o: KitchenOrder) => {
		const step = NEXT[o.kitchen_status];
		if (!step) return;
		setBusy(o.name);
		try {
			await api.setKitchenStatus(o.name, step.to);
			// Thông báo khi chuyển Chưa làm -> Đã làm
			if (step.to === "Đã làm") {
				setToast(
					`Mời khách ${o.customer_name} đến quầy nhận món` +
						(o.buzzer_number ? ` (thẻ #${o.buzzer_number})` : "")
				);
			}
			await load();
		} catch (err) {
			setError(err instanceof Error ? err.message : String(err));
		} finally {
			setBusy(null);
		}
	};

	// Toast tự tắt sau 5 giây
	useEffect(() => {
		if (!toast) return;
		const t = window.setTimeout(() => setToast(null), 5000);
		return () => window.clearTimeout(t);
	}, [toast]);

	// Lấy chi tiết đơn (có size) rồi mở xem trước phiếu pha chế
	const openTicket = async (name: string) => {
		setPrintBusy(name);
		try {
			setTicket(await api.getOrderDetail(name));
		} catch (err) {
			setError(err instanceof Error ? err.message : String(err));
		} finally {
			setPrintBusy(null);
		}
	};

	return (
		<div className="pos-kitchen">
			{error ? <div className="pos-alert pos-alert--error">{error}</div> : null}

			<div className="pos-tabs" role="tablist">
				{STEPS.map((s) => (
					<button
						key={s}
						type="button"
						className={`pos-tab ${tab === s ? "is-active" : ""}`}
						onClick={() => setTab(s)}
					>
						{s} <span className="pos-tab__count">{counts[s] || 0}</span>
					</button>
				))}
			</div>

			{loading && !list.length ? (
				<div className="pos-empty">Đang tải đơn…</div>
			) : !list.length ? (
				<div className="pos-empty">Không có đơn nào.</div>
			) : (
				<div className="pos-kitchen-grid">
					{list.map((o, idx) => {
						const w = waitInfo(o.creation, now);
						const step = NEXT[o.kitchen_status];
						return (
							<article key={o.name} className={`pos-kcard pos-kcard--${w.level}`}>
								<header className="pos-kcard__head">
									<span className="pos-kcard__seq">{idx + 1}</span>
									<div className="pos-kcard__id">
										<strong>{o.name}</strong>
										<span>{o.customer_name}</span>
									</div>
									<div className="pos-kcard__tags">
										<span className="pos-tag">{typeLabel(o.order_type)}</span>
										{o.buzzer_number ? <span className="pos-tag">Thẻ #{o.buzzer_number}</span> : null}
									</div>
								</header>

								<ul className="pos-kcard__items">
									{o.items.map((it, i) => (
										<li key={`${it.item_code}-${i}`}>
											<div className="pos-kcard__line">
												<span className="pos-kcard__qty">{it.qty}×</span>
												<span className="pos-kcard__name">{it.item_name}</span>
											</div>
											<div className="pos-kcard__opts">
												<span className="pos-chip-opt">Đường {it.sugar_level || 100}%</span>
												<span className="pos-chip-opt">Đá {it.ice_level || 100}%</span>
											</div>
										</li>
									))}
								</ul>

								{o.order_note ? <div className="pos-kcard__note">{o.order_note}</div> : null}

								<footer className="pos-kcard__foot">
									<span className={`pos-kcard__wait pos-kcard__wait--${w.level}`}>
										{w.min < 1 ? "Vừa tới" : `${w.min} phút`} · {o.creation.slice(11, 16)}
									</span>
									<div className="pos-kcard__actions">
										<button
											type="button"
											className="pos-btn pos-btn--ghost pos-kcard__print"
											disabled={printBusy === o.name}
											onClick={() => openTicket(o.name)}
										>
											{printBusy === o.name ? "Đang tải…" : "In phiếu"}
										</button>
										{step ? (
											<button
												type="button"
												className={`pos-btn pos-kcard__btn ${
													o.kitchen_status === "Chưa làm" ? "pos-btn--primary" : "pos-btn--success"
												}`}
												disabled={busy === o.name}
												onClick={() => advance(o)}
											>
												{busy === o.name ? "Đang lưu…" : step.label}
											</button>
										) : null}
									</div>
								</footer>
							</article>
						);
					})}
				</div>
			)}

			{toast ? (
				<div className="pos-toast" role="status" onClick={() => setToast(null)}>
					{toast}
				</div>
			) : null}

			<ReceiptModal order={ticket} kind="kitchen" onClose={() => setTicket(null)} />
		</div>
	);
}