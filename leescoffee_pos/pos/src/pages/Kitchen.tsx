import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { flushSync } from "react-dom";
import CupLabels, { buildCups, cupIndexes } from "../components/CupLabels";
import type { LabelJob } from "../components/CupLabels";
import { api } from "../lib/api";
import { cssVar, printWithPage } from "../lib/print";
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
	const [labelJob, setLabelJob] = useState<LabelJob | null>(null);
	const [printBusy, setPrintBusy] = useState<string | null>(null);
	// Đơn đã in tem ít nhất một lần (chỉ trong state, mất khi tải lại trang)
	const [printed, setPrinted] = useState<Set<string>>(() => new Set());
	// Chi tiết đơn (có size) đã tải, tránh gọi lại mỗi lần in
	const details = useRef(new Map<string, OrderDetail>());

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

	// In tem từng ly: cả đơn (only = undefined) hoặc một ly (only = số ly i).
	const printCups = async (o: KitchenOrder, only?: number) => {
		setPrintBusy(o.name);
		try {
			let d = details.current.get(o.name);
			if (!d) {
				d = await api.getOrderDetail(o.name);
				details.current.set(o.name, d);
			}
			const all = buildCups(o, d);
			const cups = only ? all.filter((c) => c.i === only) : all;
			if (!cups.length) return;

			flushSync(() => setLabelJob({ order: o, cups }));
			const size = `${cssVar("--pos-label-width", "50mm")} ${cssVar("--pos-label-height", "30mm")}`;
			printWithPage(size, {
				bodyClass: "is-printing-labels",
				onAfter: () => {
					setPrinted((prev) => new Set(prev).add(o.name));
					setLabelJob(null);
				},
			});
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
					{list.map((o) => {
						const w = waitInfo(o.creation, now);
						const step = NEXT[o.kitchen_status];
						// Chỉ tab Chưa làm được in tem; "Đã làm" khóa tới khi đã in ít nhất một lần.
						const canPrint = o.kitchen_status === "Chưa làm";
						const needPrint = canPrint && !printed.has(o.name);
						const cupsOf = canPrint ? cupIndexes(o) : null;
						const loadingPrint = printBusy === o.name;
						return (
							<article key={o.name} className={`pos-kcard pos-kcard--${w.level}`}>
								<header className="pos-kcard__head">
									<div className="pos-kcard__id">
										<strong>{o.name}</strong>
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
											{cupsOf ? (
												<div className="pos-kcard__cups">
													{cupsOf.per[i].map((n) => (
														<button
															key={n}
															type="button"
															className="pos-kcard__cup-print"
															title={`In tem ly ${n}/${cupsOf.n}`}
															disabled={loadingPrint}
															onClick={() => printCups(o, n)}
														>
															In {n}/{cupsOf.n}
														</button>
													))}
												</div>
											) : null}
										</li>
									))}
								</ul>

								{o.order_note ? <div className="pos-kcard__note">{o.order_note}</div> : null}

								<footer className="pos-kcard__foot">
									<span className={`pos-kcard__wait pos-kcard__wait--${w.level}`}>
										{w.min < 1 ? "Vừa tới" : `${w.min} phút`} · {o.creation.slice(11, 16)}
									</span>
									<div className="pos-kcard__actions">
										{canPrint ? (
											<button
												type="button"
												className="pos-btn pos-btn--ghost pos-kcard__print"
												disabled={loadingPrint}
												onClick={() => printCups(o)}
											>
												{loadingPrint ? "Đang tải…" : "In tất cả tem"}
											</button>
										) : null}
										{step ? (
											<button
												type="button"
												className={`pos-btn pos-kcard__btn ${
													o.kitchen_status === "Chưa làm" ? "pos-btn--primary" : "pos-btn--success"
												}`}
												disabled={busy === o.name || needPrint}
												title={needPrint ? "In tem trước" : undefined}
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

			<CupLabels job={labelJob} />
		</div>
	);
}