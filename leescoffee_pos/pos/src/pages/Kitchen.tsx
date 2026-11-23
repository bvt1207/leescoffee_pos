import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { flushSync } from "react-dom";
import CupLabels, { buildCups, cupIndexes } from "../components/CupLabels";
import OrderTypeChip, { ChannelChip, typeModifier } from "../components/OrderTypeChip";
import type { LabelJob } from "../components/CupLabels";
import ReceiptModal from "../components/ReceiptModal";
import { api } from "../lib/api";
import { optionParts } from "../lib/options";
import { kitchenTabsOf, kitchenTransitionsOf, usePos } from "../lib/pos-context";
import { cssVar, printWithPage } from "../lib/print";
import { refreshServeQueue } from "../lib/serve";
import { useServeQueue } from "../store/serveQueue";
import { shortOrderNo } from "../lib/format";
import type { KitchenOrder, KitchenStep, OrderDetail } from "../types";

type Step = KitchenStep;


function parseTime(s: string): number {
	return new Date(s.replace(" ", "T")).getTime();
}

function waitInfo(creation: string, now: number) {
	const min = Math.max(0, Math.floor((now - parseTime(creation)) / 60000));
	const level = min >= 10 ? "late" : min >= 5 ? "warn" : "ok";
	return { min, level };
}

export default function Kitchen() {
	const { config } = usePos();
	// Tab và bước chuyển theo role, lấy từ get_pos_config (backend vẫn kiểm tra lại).
	const tabs = kitchenTabsOf(config);
	const transitions = kitchenTransitionsOf(config);
	const nextOf = useCallback(
		(from: string) => transitions.find((t) => t.from === from),
		[transitions]
	);

	const [orders, setOrders] = useState<KitchenOrder[]>([]);
	const [tab, setTab] = useState<Step>(() => tabs[0] ?? "Chưa làm");
	const [busy, setBusy] = useState<string | null>(null);
	const [error, setError] = useState("");
	const [loading, setLoading] = useState(true);
	const [now, setNow] = useState(Date.now());
	const [toast, setToast] = useState<string | null>(null);
	const [labelJob, setLabelJob] = useState<LabelJob | null>(null);
	// Phiếu pha chế tổng đang xem trước (modal)
	const [ticket, setTicket] = useState<OrderDetail | null>(null);
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

	// Tab đang chọn không còn được phép (đổi user / tải lại config) -> về tab đầu tiên được phép.
	useEffect(() => {
		if (tabs.length && !tabs.includes(tab)) setTab(tabs[0]);
	}, [tabs, tab]);

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
		const step = nextOf(o.kitchen_status);
		if (!step) return;
		setBusy(o.name);
		try {
			await api.setKitchenStatus(o.name, step.to);
			// Chấm đỏ "Pha chế" (hàng chờ của thu ngân): đơn rời "Đã làm" -> bỏ khỏi store ngay, không đợi poll, không thêm request.
			if (step.to !== "Đã làm") useServeQueue.getState().dropItems([o.name]);
			// Chưa làm -> Đã làm: thu ngân nhận thông báo (hàng chờ phục vụ, poll ở máy quầy). Màn này chỉ xác nhận đã báo.
			// Đơn QR: khách tự nhận thông báo trên điện thoại và tới quầy (luồng QR không đổi).
			if (step.to === "Đã làm") {
				setToast(
					o.order_channel === "QR"
						? `Đã báo khách ${o.customer_name} (đặt QR) tới quầy nhận món`
						: o.order_type === "Dine In" && o.buzzer_number
							? `Đã báo quầy phục vụ: Bàn ${o.buzzer_number}`
							: `Đã báo quầy gọi khách ${shortOrderNo(o.name)}`
				);
				// Máy có role CASHIER -> cập nhật chấm đỏ ngay, KHÔNG bật toast thứ hai cho chính đơn này (đã có toast ở trên).
				// KITCHEN-only: store tắt, không gọi API.
				void refreshServeQueue([o.name]).catch(() => undefined);
			}
			await load();
		} catch (err) {
			setError(err instanceof Error ? err.message : String(err));
		} finally {
			setBusy(null);
		}
	};


	const markPrinted = useCallback((name: string) => {
		setPrinted((prev) => new Set(prev).add(name));
	}, []);

	const closeTicket = useCallback(() => setTicket(null), []);

	// Chi tiết đơn (có size), lấy một lần rồi giữ trong cache
	const getDetail = async (name: string) => {
		let d = details.current.get(name);
		if (!d) {
			d = await api.getOrderDetail(name);
			details.current.set(name, d);
		}
		return d;
	};

	// In tem: mỗi lần bấm "In i/n" chỉ ra đúng 1 tem (1 trang).
	const printCup = async (o: KitchenOrder, cupNo: number) => {
		setPrintBusy(o.name);
		try {
			const cups = buildCups(o, await getDetail(o.name)).filter((c) => c.i === cupNo);
			if (!cups.length) return;

			flushSync(() => setLabelJob({ order: o, cups }));
			const size = `${cssVar("--pos-label-width", "50mm")} ${cssVar("--pos-label-height", "30mm")}`;
			printWithPage(size, {
				bodyClass: "is-printing-labels",
				onAfter: () => {
					markPrinted(o.name);
					setLabelJob(null);
				},
			});
		} catch (err) {
			setError(err instanceof Error ? err.message : String(err));
		} finally {
			setPrintBusy(null);
		}
	};

	// "In phiếu": mở modal phiếu pha chế tổng cho cả đơn.
	const openTicket = async (o: KitchenOrder) => {
		setPrintBusy(o.name);
		try {
			setTicket(await getDetail(o.name));
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
				{tabs.map((s) => (
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
						// Chỉ có nút khi role được phép bước này; tab chỉ xem thì không có nút.
						const step = nextOf(o.kitchen_status);
						// Chỉ tab Chưa làm được in tem; "Đã làm" khóa tới khi đã in ít nhất một lần.
						const canPrint = o.kitchen_status === "Chưa làm";
						const needPrint = canPrint && !printed.has(o.name);
						const cupsOf = canPrint ? cupIndexes(o) : null;
						const loadingPrint = printBusy === o.name;
						return (
							<article
								key={o.name}
								className={`pos-kcard pos-kcard--${w.level} pos-kcard--${typeModifier(o.order_type)}`}
							>
								<header className="pos-kcard__head">
									<div className="pos-kcard__id">
										<strong>{o.name}</strong>
									</div>
									<div className="pos-kcard__tags">
										<OrderTypeChip type={o.order_type} />
										<ChannelChip channel={o.order_channel} />
										{o.buzzer_number ? <span className="pos-tag">Bàn #{o.buzzer_number}</span> : null}
									</div>
								</header>

								<ul className="pos-kcard__items">
									{o.items.map((it, i) => (
										<li key={`${it.item_code}-${i}`}>
											<div className="pos-kcard__line">
												<span className="pos-kcard__qty">{it.qty}×</span>
												<span className="pos-kcard__name">{it.item_name}</span>
											</div>
											{optionParts(it.options).length ? (
												<div className="pos-kcard__opts">
													{optionParts(it.options).map((part) => (
														<span key={part} className="pos-chip-opt">
															{part}
														</span>
													))}
												</div>
											) : null}
											{cupsOf ? (
												<div className="pos-kcard__cups">
													{cupsOf.per[i].map((n) => (
														<button
															key={n}
															type="button"
															className="pos-kcard__cup-print"
															title={`In tem ly ${n}/${cupsOf.n}`}
															disabled={loadingPrint}
															onClick={() => printCup(o, n)}
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
												onClick={() => openTicket(o)}
											>
												{loadingPrint ? "Đang tải…" : "In phiếu"}
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
												{busy === o.name ? "Đang lưu…" : step.to}
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
			<ReceiptModal
				key={ticket?.name || "none"}
				order={ticket}
				kind="kitchen"
				onPrinted={ticket ? () => markPrinted(ticket.name) : undefined}
				onClose={closeTicket}
			/>
		</div>
	);
}