import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import OrderTypeChip, { ChannelChip, isQrOrder } from "../components/OrderTypeChip";
import QrModal from "../components/QrModal";
import ReceiptModal from "../components/ReceiptModal";
import { api } from "../lib/api";
import { addDaysIso, autoCancelInfo, customerLabel, formatOrderTime, orderMatches, shortOrderNo, SITE_TZ, todayIso } from "../lib/format";
import { formatOptions, lineUnitSurcharge } from "../lib/options";
import { usePos } from "../lib/pos-context";
import { formatMoney } from "../store/cart";
import { useOrderFilter } from "../store/orderFilter";
import { useSearch } from "../store/search";
import type { OrderDetail, OrderSummary, OrdersSummary, QrInfo } from "../types";

type Tab = "draft" | "paid";

/** Ca hiện tại: số đơn tối đa mỗi tab (backend kẹp ở ORDERS_MAX_LIMIT = 200). */
const SHIFT_LIMIT = 200;
/** Lịch sử: số đơn mỗi lần tải ("Xem thêm" tải tiếp). */
const HISTORY_PAGE = 100;
/** Chờ người dùng gõ xong ô tìm kiếm trước khi hỏi server (chế độ Lịch sử). */
const SEARCH_DEBOUNCE_MS = 350;
/** Lý do hủy đơn Draft — khớp order_cancel.MANUAL_REASONS ở backend (pos_invoice_hooks/order_cancel.py). "Khác" bắt buộc ghi chú. */
const CANCEL_REASONS = ["Khách đổi ý", "Đặt nhầm", "Khách không lấy", "Khác"] as const;
const REASON_OTHER = "Khác";
/** Thẻ đơn hiện nhãn "Tự hủy sau …" khi còn ít hơn số phút này. */
const AUTO_CANCEL_WARN_MINUTES = 30;

// Món có CTKM: giá gốc (price_list_rate) cao hơn giá bán (rate) do server trả.
const itemPromo = (it: OrderDetail["items"][number]) =>
	(it.discount_percentage ?? 0) > 0 || (it.price_list_rate ?? 0) > it.rate;
const promoTotal = (items: OrderDetail["items"]) =>
	items.reduce(
		(sum, it) => sum + (itemPromo(it) ? ((it.price_list_rate ?? 0) - it.rate) * it.qty : 0),
		0
	);

export default function Orders() {
	const [params] = useSearchParams();
	const draftParam = params.get("draft");
	const search = useSearch((s) => s.search).trim().toLowerCase();
	const { config } = usePos();
	const tz = config?.time_zone || SITE_TZ;
	const isManager = !!config?.roles?.manager;

	// Bộ lọc nhớ khi chuyển trang (zustand). Lịch sử chỉ dành cho MANAGER (backend cũng chặn).
	const storedMode = useOrderFilter((s) => s.mode);
	const mode = isManager ? storedMode : "shift";
	const preset = useOrderFilter((s) => s.preset);
	const day = useOrderFilter((s) => s.day);
	const setMode = useOrderFilter((s) => s.setMode);
	const setPreset = useOrderFilter((s) => s.setPreset);
	const setDay = useOrderFilter((s) => s.setDay);

	const [tab, setTab] = useState<Tab>("draft");
	const [drafts, setDrafts] = useState<OrderSummary[]>([]);
	const [paid, setPaid] = useState<OrderSummary[]>([]);
	const [shiftInfo, setShiftInfo] = useState<OrdersSummary | null>(null);
	const [history, setHistory] = useState<OrderSummary[]>([]);
	const [historyInfo, setHistoryInfo] = useState<OrdersSummary | null>(null);
	const [historyLoading, setHistoryLoading] = useState(false);
	const [historySearch, setHistorySearch] = useState(search);
	const [selected, setSelected] = useState<string | null>(draftParam || null);
	const [detail, setDetail] = useState<OrderDetail | null>(null);
	const [qr, setQr] = useState<QrInfo | null>(null);
	const [confirmCancel, setConfirmCancel] = useState(false);
	const [cancelReason, setCancelReason] = useState("");
	const [cancelNote, setCancelNote] = useState("");
	const [receipt, setReceipt] = useState<{ order: OrderDetail; forced: boolean } | null>(null);
	const [busy, setBusy] = useState(false);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");
	// Đơn đang chờ thanh toán QR — khi xuất hiện trong danh sách đã thanh toán thì mở in bắt buộc.
	const awaitingQr = useRef<string | null>(null);
	// Số thứ tự request Lịch sử: bỏ kết quả về muộn của bộ lọc cũ.
	const historySeq = useRef(0);

	const closeReceipt = useCallback(() => setReceipt(null), []);

	// Sau khi thanh toán: về Ca hiện tại, tab Đã thanh toán, chọn đúng đơn, mở hóa đơn bắt buộc in.
	const openPaid = useCallback(
		async (name: string) => {
			if (awaitingQr.current === name) awaitingQr.current = null;
			const d = await api.getOrderDetail(name);
			setQr(null);
			setMode("shift");
			setTab("paid");
			setSelected(name);
			setDetail(d);
			setReceipt({ order: d, forced: true });
		},
		[setMode]
	);

	const loadDetail = useCallback(async (name: string | null) => {
		if (!name) {
			setDetail(null);
			return;
		}
		try {
			setDetail(await api.getOrderDetail(name));
		} catch {
			setDetail(null);
		}
	}, []);

	// Ca hiện tại: 2 danh sách + bộ đếm/thông tin ca (3 request mỗi 10 giây).
	const loadData = useCallback(async () => {
		try {
			const [d, p, info] = await Promise.all([
				api.getOrders({ status: "draft", limit: SHIFT_LIMIT }),
				api.getOrders({ status: "paid", limit: SHIFT_LIMIT }),
				api.getOrdersSummary({ scope: "shift" }),
			]);
			setDrafts((d || []).filter((o) => o.docstatus === 0));
			setPaid(p || []);
			setShiftInfo(info);
			setError("");

			const waiting = awaitingQr.current;
			if (waiting && (p || []).some((o) => o.name === waiting)) {
				await openPaid(waiting);
			}
		} catch (err) {
			setError(err instanceof Error ? err.message : String(err));
		} finally {
			setLoading(false);
		}
	}, [openPaid]);

	useEffect(() => {
		if (mode !== "shift") return;
		loadData();
		const timer = window.setInterval(loadData, 10000);
		return () => window.clearInterval(timer);
	}, [mode, loadData]);

	// Khoảng ngày Lịch sử theo múi giờ site.
	const range = useMemo(() => {
		const today = todayIso(tz);
		if (preset === "7d") return { from: addDaysIso(today, -6), to: today };
		if (preset === "day" && day) return { from: day, to: day };
		const yesterday = addDaysIso(today, -1);
		return { from: yesterday, to: yesterday };
	}, [preset, day, tz]);

	useEffect(() => {
		const timer = window.setTimeout(() => setHistorySearch(search), SEARCH_DEBOUNCE_MS);
		return () => window.clearTimeout(timer);
	}, [search]);

	// Lịch sử: tải theo bộ lọc (không poll — dữ liệu ngày cũ không đổi). start > 0 = "Xem thêm".
	const loadHistory = useCallback(
		async (start: number) => {
			const seq = ++historySeq.current;
			setHistoryLoading(true);
			const query = {
				scope: "history" as const,
				from_date: range.from,
				to_date: range.to,
				search: historySearch,
			};
			try {
				const [rows, info] = await Promise.all([
					api.getOrders({ ...query, limit: HISTORY_PAGE, start }),
					start === 0 ? api.getOrdersSummary(query) : Promise.resolve(null),
				]);
				if (seq !== historySeq.current) return;
				setHistory((prev) => {
					if (start === 0) return rows || [];
					const seen = new Set(prev.map((o) => o.name));
					return [...prev, ...(rows || []).filter((o) => !seen.has(o.name))];
				});
				if (info) setHistoryInfo(info);
				setError("");
			} catch (err) {
				if (seq === historySeq.current) setError(err instanceof Error ? err.message : String(err));
			} finally {
				if (seq === historySeq.current) setHistoryLoading(false);
			}
		},
		[range.from, range.to, historySearch]
	);

	useEffect(() => {
		if (mode === "history") loadHistory(0);
	}, [mode, loadHistory]);

	useEffect(() => {
		loadDetail(selected);
		const timer = window.setInterval(() => loadDetail(selected), 10000);
		return () => window.clearInterval(timer);
	}, [selected, loadDetail]);

	useEffect(() => {
		if (draftParam) {
			setMode("shift");
			setSelected(draftParam);
			setTab("draft");
		}
	}, [draftParam, setMode]);

	const list = useMemo(
		() =>
			mode === "history"
				? history
				: (tab === "draft" ? drafts : paid).filter((o) => orderMatches(o, search)),
		[mode, history, tab, drafts, paid, search]
	);

	// Bộ đếm tab: COUNT của server; khi đang tìm thì đếm theo danh sách đã lọc.
	const draftCount = search
		? drafts.filter((o) => orderMatches(o, search)).length
		: shiftInfo?.counts.draft ?? drafts.length;
	const paidCount = search
		? paid.filter((o) => orderMatches(o, search)).length
		: shiftInfo?.counts.paid ?? paid.length;
	const historyTotal = historyInfo?.counts.paid ?? 0;
	const noShift = mode === "shift" && shiftInfo !== null && !shiftInfo.shift;

	const run = async (action: () => Promise<void>) => {
		setBusy(true);
		setError("");
		try {
			await action();
		} catch (err) {
			setError(err instanceof Error ? err.message : String(err));
		} finally {
			setBusy(false);
		}
	};

	const refresh = async (name: string) => {
		await loadData();
		await loadDetail(name);
	};

	const payCash = () =>
		run(async () => {
			if (!detail) return;
			const name = detail.name;
			await api.payCash(name);
			await loadData();
			await openPaid(name);
		});

	const genQr = () =>
		run(async () => {
			if (!detail) return;
			awaitingQr.current = detail.name;
			setQr(await api.generateQr(detail.name));
			await refresh(detail.name);
		});


	const openCancel = () => {
		setCancelReason("");
		setCancelNote("");
		setConfirmCancel(true);
	};
	const canCancel = !!cancelReason && (cancelReason !== REASON_OTHER || cancelNote.trim().length > 0);

	const cancelOrder = () =>
		run(async () => {
			if (!detail || !canCancel) return;
			const waiting = detail.payment_status === "Đang chờ";
			await api.cancelDraftOrder(detail.name, waiting ? 1 : 0, cancelReason, cancelNote.trim());
			if (awaitingQr.current === detail.name) awaitingQr.current = null;
			setConfirmCancel(false);
			setSelected(null);
			setDetail(null);
			await loadData();
		});

	const isDraft = detail?.docstatus === 0;
	const waitingQr = detail?.payment_status === "Đang chờ";
	// Draft kênh khác QR tự hủy sau pos_draft_auto_cancel_minutes (job backend); QR có hạn riêng.
	const autoCancelMinutes = config?.pos_draft_auto_cancel_minutes ?? 0;
	const autoCancelOf = (o: { docstatus: number; order_channel?: string; creation: string }) =>
		o.docstatus === 0 && !isQrOrder(o.order_channel) ? autoCancelInfo(o.creation, autoCancelMinutes, tz) : null;
	const detailAutoCancel = detail ? autoCancelOf(detail) : null;

		return (
		<div className="pos-orders-page">
			{error ? <div className="pos-alert pos-alert--error">{error}</div> : null}

			<div className="pos-orders-bar">
				{isManager ? (
					<div className="pos-segmented pos-orders-mode" role="group" aria-label="Chế độ xem đơn">
						<button
							type="button"
							className={mode === "shift" ? "is-active" : ""}
							aria-pressed={mode === "shift"}
							onClick={() => setMode("shift")}
						>
							Ca hiện tại
						</button>
						<button
							type="button"
							className={mode === "history" ? "is-active" : ""}
							aria-pressed={mode === "history"}
							onClick={() => setMode("history")}
						>
							Lịch sử
						</button>
					</div>
				) : null}

				{mode === "shift" ? (
					<div className="pos-tabs" role="tablist">
						<button type="button" className={`pos-tab ${tab === "draft" ? "is-active" : ""}`} onClick={() => setTab("draft")}>
							Chờ thanh toán <span className="pos-tab__count">{draftCount}</span>
						</button>
						<button type="button" className={`pos-tab ${tab === "paid" ? "is-active" : ""}`} onClick={() => setTab("paid")}>
							Đã thanh toán <span className="pos-tab__count">{paidCount}</span>
						</button>
					</div>
				) : (
					<div className="pos-orders-filter" role="group" aria-label="Khoảng ngày">
						<button
							type="button"
							className={`pos-tab ${preset === "yesterday" ? "is-active" : ""}`}
							onClick={() => setPreset("yesterday")}
						>
							Hôm qua
						</button>
						<button
							type="button"
							className={`pos-tab ${preset === "7d" ? "is-active" : ""}`}
							onClick={() => setPreset("7d")}
						>
							7 ngày
						</button>
						<label className={`pos-tab pos-orders-filter__day ${preset === "day" ? "is-active" : ""}`}>
							<span>Chọn ngày</span>
							<input
								type="date"
								className="pos-orders-filter__date"
								value={preset === "day" ? day : ""}
								max={todayIso(tz)}
								onChange={(event) => {
									if (event.target.value) setDay(event.target.value);
								}}
							/>
						</label>
						<span className="pos-orders-filter__count">
							{historyLoading && !historyInfo ? "Đang tải…" : `${historyTotal} đơn`}
						</span>
					</div>
				)}
			</div>

			{mode === "shift" && shiftInfo ? (
				<div className="pos-orders-shift">
					{shiftInfo.shift
						? `Ca mở lúc ${formatOrderTime(shiftInfo.shift.period_start_date, tz)}`
						: "Chưa mở ca bán hàng. Ca sẽ mở khi tạo đơn đầu tiên."}
				</div>
			) : null}

			{mode === "shift" && isManager && (shiftInfo?.old_drafts ?? 0) > 0 ? (
				<div className="pos-alert pos-alert--warn">
					Còn {shiftInfo?.old_drafts} đơn chờ thanh toán của ca trước (không hiện ở Ca hiện tại). Xử lý trong Desk:
					POS Invoice, lọc Draft.
				</div>
			) : null}

			<div className="pos-orders-layout">
				<section className="pos-orders-list">
					{(mode === "shift" ? loading : historyLoading) && !list.length ? (
						<div className="pos-empty">Đang tải đơn hàng…</div>
					) : list.length ? (
						<div className="pos-order-grid">
							{list.map((o) => (
								<button
									type="button"
									key={o.name}
									className={`pos-order-card ${selected === o.name ? "is-active" : ""}`}
									onClick={() => {
										// Chọn đơn Draft tại quầy -> màn khách (/pos/customer) hiện đơn đó. Chỉ gọi khi đổi đơn.
										if (selected !== o.name && o.docstatus === 0 && o.order_channel !== "QR") {
											void api.setCustomerDisplay("order", o.name).catch(() => undefined);
										}
										setSelected(o.name);
									}}
								>
									<div className="pos-order-card__top">
										<strong>{customerLabel(o)}</strong>
										<span className="pos-order-card__price">{formatMoney(o.amount, o.currency)}</span>
									</div>
									<div className="pos-order-card__meta">
										<span className="pos-order-card__no" title={o.name}>
											{shortOrderNo(o.name)}
										</span>
										<OrderTypeChip type={o.order_type} />
										<ChannelChip channel={o.order_channel} />
										{o.buzzer_number ? <span className="pos-tag">Bàn #{o.buzzer_number}</span> : null}
										{o.payment_status === "Đang chờ" ? <span className="pos-tag pos-tag--warn">Chờ QR</span> : null}
										{o.custom_kitchen_status ? <span className="pos-status__badge">{o.custom_kitchen_status}</span> : null}
										{o.status === "Consolidated" ? <span className="pos-tag">Đã đóng ca</span> : null}
										{(() => {
											const ac = autoCancelOf(o);
											if (!ac || ac.remaining > AUTO_CANCEL_WARN_MINUTES) return null;
											return (
												<span className="pos-tag pos-tag--warn" title={`Tự hủy lúc ${ac.at} nếu chưa thanh toán`}>
													{ac.remaining > 0 ? `Tự hủy sau ${ac.remaining} phút` : "Sắp tự hủy"}
												</span>
											);
										})()}
										<span className="pos-order-card__time">{formatOrderTime(o.creation, tz)}</span>
									</div>
								</button>
							))}
						</div>
					) : (
						<div className="pos-empty">
							{search
								? "Không tìm thấy đơn phù hợp."
								: mode === "history"
									? "Không có đơn đã thanh toán trong khoảng ngày này."
									: noShift
										? "Chưa mở ca bán hàng."
										: tab === "draft"
											? "Không có đơn nào chờ thanh toán trong ca."
											: "Chưa có đơn đã thanh toán trong ca."}
						</div>
					)}
					{mode === "history" && history.length < historyTotal ? (
						<button
							type="button"
							className="pos-btn pos-orders-more"
							disabled={historyLoading}
							onClick={() => loadHistory(history.length)}
						>
							{historyLoading ? "Đang tải…" : `Xem thêm (${history.length}/${historyTotal})`}
						</button>
					) : null}
				</section>

				<aside className="pos-order-detail">
					{detail ? (
						<>
							<div className="pos-order-detail__head">
								<div>
									<div className="pos-order-detail__name">{customerLabel(detail)}</div>
									<div className="pos-order-detail__sub">
										{detail.name} · {formatOrderTime(detail.creation, tz)} · <OrderTypeChip type={detail.order_type} /> <ChannelChip channel={detail.order_channel} />
										{detail.order_type === "Dine In" && !isQrOrder(detail.order_channel)
											? ` · Bàn #${detail.buzzer_number || "—"}`
											: ""}
									</div>
								</div>
								<span className={isDraft ? "pos-pending" : "pos-ok"}>
									{isDraft
										? "Chờ thanh toán"
										: detail.status === "Consolidated"
											? "Đã đóng ca"
											: detail.status || "Đã thanh toán"}
								</span>
							</div>

							<div className="pos-order-detail__items">
								{detail.items.map((it, i) => (
									<div key={`${it.item_code}-${i}`} className="pos-detail__row pos-detail__row--item">
										<div className="pos-detail__item-main">
											<span>{it.item_name}</span>
											{formatOptions(it.options, true) ? (
												<small className="pos-detail__opts">{formatOptions(it.options, true)}</small>
											) : null}
										</div>
										<span>x{it.qty}</span>
										<strong>
											{itemPromo(it) ? (
												<span className="pos-price-old">
													{formatMoney(((it.price_list_rate ?? 0) + lineUnitSurcharge(it.options)) * it.qty, detail.currency)}
												</span>
											) : null}
											{/* Giá dòng gồm phụ thu topping (server lưu ở dòng Actual, cộng sau CTKM). */}
											{formatMoney(it.amount + lineUnitSurcharge(it.options) * it.qty, detail.currency)}
											{(it.discount_percentage ?? 0) > 0 ? (
												<span className="pos-promo-chip">−{it.discount_percentage}%</span>
											) : null}
										</strong>
									</div>
								))}
							</div>

							{promoTotal(detail.items) > 0 ? (
								<div className="pos-detail__row pos-detail__row--promo">
									<span>Khuyến mãi</span>
									<span>−{formatMoney(promoTotal(detail.items), detail.currency)}</span>
								</div>
							) : null}
							{(detail.total_surcharge ?? 0) > 0 ? (
								<div className="pos-detail__row">
									<span>Gồm phụ thu topping</span>
									<span>{formatMoney(detail.total_surcharge ?? 0, detail.currency)}</span>
								</div>
							) : null}
							{(detail.discount_amount ?? 0) > 0 ? (
								<div className="pos-detail__row pos-detail__row--promo">
									<span>
										Đổi điểm{detail.redeemed_points ? ` (${detail.redeemed_points} điểm)` : ""}
									</span>
									<span>−{formatMoney(detail.discount_amount ?? 0, detail.currency)}</span>
								</div>
							) : null}

							<div className="pos-order-detail__total">
								<span>Tổng cộng</span>
								<strong>{formatMoney(detail.grand_total, detail.currency)}</strong>
							</div>

							{detail.order_note ? (
								<div className="pos-order-detail__note">
									<strong>Ghi chú:</strong> {detail.order_note}
								</div>
							) : null}

							{detail.custom_kitchen_status ? (
								<div className="pos-order-detail__kitchen">Bếp: {detail.custom_kitchen_status}</div>
							) : null}

							{isDraft && detailAutoCancel ? (
								<div className="pos-order-detail__auto">
									{detailAutoCancel.remaining > 0
										? `Tự hủy lúc ${detailAutoCancel.at} nếu chưa thanh toán`
										: "Đơn đã quá hạn, sẽ tự hủy trong vài phút nếu chưa thanh toán"}
								</div>
							) : null}

							<div className="pos-order-detail__actions">
								{isDraft ? (
									<>
										<button type="button" className="pos-btn pos-btn--primary" disabled={busy} onClick={payCash}>
											Thu tiền mặt
										</button>
										<button type="button" className="pos-btn" disabled={busy} onClick={genQr}>
											Thanh toán QR
										</button>
										<button type="button" className="pos-btn pos-btn--danger" disabled={busy} onClick={openCancel}>
											Hủy đơn
										</button>
									</>
								) : null}
								{!isDraft ? (
									<button
										type="button"
										className="pos-btn"
										disabled={busy}
										onClick={() => setReceipt({ order: detail, forced: false })}
									>
										In
									</button>
								) : null}
							</div>
						</>
					) : (
						<div className="pos-empty">Chọn một đơn để xem chi tiết.</div>
					)}
				</aside>
			</div>

			{confirmCancel && detail ? (
				<div className="pos-modal-backdrop" onClick={() => setConfirmCancel(false)}>
					<div className="pos-modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
						<div className="pos-modal__header">
							<h3>Hủy đơn {detail.name}?</h3>
							<button type="button" className="pos-modal__close" aria-label="Đóng" onClick={() => setConfirmCancel(false)}>
								×
							</button>
						</div>
						<div className="pos-confirm">
							<p>
								Đơn sẽ bị hủy và lưu lại để đối soát.
								{detail.order_type === "Dine In" ? " Thẻ bàn sẽ được trả về." : ""}
							</p>
							<fieldset className="pos-reason">
								<legend className="pos-reason__legend">Lý do hủy</legend>
								{CANCEL_REASONS.map((r) => (
									<label key={r} className={`pos-reason__option${cancelReason === r ? " is-active" : ""}`}>
										<input
											type="radio"
											name="cancel-reason"
											value={r}
											checked={cancelReason === r}
											onChange={() => setCancelReason(r)}
										/>
										<span>{r}</span>
									</label>
								))}
							</fieldset>
							{cancelReason === REASON_OTHER ? (
								<textarea
									className="pos-input pos-textarea"
									rows={2}
									placeholder="Ghi chú lý do (bắt buộc)"
									aria-label="Ghi chú lý do hủy"
									value={cancelNote}
									onChange={(event) => setCancelNote(event.target.value)}
									autoFocus
								/>
							) : null}
							{waitingQr ? (
								<div className="pos-alert pos-alert--error">
									Đơn đang chờ thanh toán QR. Hãy chắc chắn khách chưa chuyển tiền.
								</div>
							) : null}
							<div className="pos-confirm__actions">
								<button type="button" className="pos-btn" onClick={() => setConfirmCancel(false)}>
									Giữ đơn
								</button>
								<button type="button" className="pos-btn pos-btn--danger-solid" disabled={busy || !canCancel} onClick={cancelOrder}>
									{busy ? "Đang hủy…" : "Hủy đơn"}
								</button>
							</div>
						</div>
					</div>
				</div>
			) : null}

			<QrModal qr={qr} onClose={() => setQr(null)} />
			<ReceiptModal
				key={receipt ? `${receipt.order.name}-${receipt.forced}` : "none"}
				order={receipt?.order ?? null}
				forced={receipt?.forced}
				onClose={closeReceipt}
			/>
		</div>
	);
}