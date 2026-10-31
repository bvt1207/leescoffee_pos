import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import QrModal from "../components/QrModal";
import ReceiptModal from "../components/ReceiptModal";
import { api } from "../lib/api";
import { formatMoney } from "../store/cart";
import { useSearch } from "../store/search";
import type { OrderDetail, OrderSummary, QrInfo, StatusBoardRow } from "../types";

type Tab = "draft" | "paid" | "kitchen";

const typeLabel = (t: string) => (t === "Take Away" ? "Mang đi" : "Tại quán");
const timeLabel = (iso: string) => (iso ? String(iso).slice(11, 16) : "");

export default function Orders() {
	const [params] = useSearchParams();
	const draftParam = params.get("draft");
	const search = useSearch((s) => s.search).trim().toLowerCase();

	const [tab, setTab] = useState<Tab>("draft");
	const [drafts, setDrafts] = useState<OrderSummary[]>([]);
	const [paid, setPaid] = useState<OrderSummary[]>([]);
	const [board, setBoard] = useState<StatusBoardRow[]>([]);
	const [selected, setSelected] = useState<string | null>(draftParam || null);
	const [detail, setDetail] = useState<OrderDetail | null>(null);
	const [qr, setQr] = useState<QrInfo | null>(null);
	const [confirmCancel, setConfirmCancel] = useState(false);
	const [printing, setPrinting] = useState(false);
	const [busy, setBusy] = useState(false);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");

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

	const loadData = useCallback(async () => {
		try {
			const [d, p, b] = await Promise.all([
				api.getOrders("draft"),
				api.getOrders("paid"),
				api.getStatusBoard(),
			]);
			setDrafts((d || []).filter((o) => o.docstatus === 0));
			setPaid(p || []);
			setBoard(b || []);
			setError("");
		} catch (err) {
			setError(err instanceof Error ? err.message : String(err));
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		loadData();
		const timer = window.setInterval(loadData, 10000);
		return () => window.clearInterval(timer);
	}, [loadData]);

	useEffect(() => {
		loadDetail(selected);
		const timer = window.setInterval(() => loadDetail(selected), 10000);
		return () => window.clearInterval(timer);
	}, [selected, loadDetail]);

	useEffect(() => {
		if (draftParam) {
			setSelected(draftParam);
			setTab("draft");
		}
	}, [draftParam]);

	const matches = (o: OrderSummary) =>
		!search ||
		o.name.toLowerCase().includes(search) ||
		(o.customer_name || "").toLowerCase().includes(search);

	const list = useMemo(
		() => (tab === "draft" ? drafts : paid).filter(matches),
		// eslint-disable-next-line react-hooks/exhaustive-deps
		[tab, drafts, paid, search]
	);

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
			await api.payCash(detail.name);
			await refresh(detail.name);
		});

	const genQr = () =>
		run(async () => {
			if (!detail) return;
			setQr(await api.generateQr(detail.name));
			await refresh(detail.name);
		});

	const pickup = () =>
		run(async () => {
			if (!detail) return;
			await api.confirmPickup(detail.name);
			await refresh(detail.name);
		});

	const cancelOrder = () =>
		run(async () => {
			if (!detail) return;
			const waiting = detail.payment_status === "Đang chờ";
			await api.cancelDraftOrder(detail.name, waiting ? 1 : 0);
			setConfirmCancel(false);
			setSelected(null);
			setDetail(null);
			await loadData();
		});

	const isDraft = detail?.docstatus === 0;
	const waitingQr = detail?.payment_status === "Đang chờ";

		return (
		<div className="pos-orders-page">
			{error ? <div className="pos-alert pos-alert--error">{error}</div> : null}

			<div className="pos-tabs" role="tablist">
				<button type="button" className={`pos-tab ${tab === "draft" ? "is-active" : ""}`} onClick={() => setTab("draft")}>
					Chờ thanh toán <span className="pos-tab__count">{drafts.length}</span>
				</button>
				<button type="button" className={`pos-tab ${tab === "paid" ? "is-active" : ""}`} onClick={() => setTab("paid")}>
					Đã thanh toán <span className="pos-tab__count">{paid.length}</span>
				</button>
			</div>

			<div className="pos-orders-layout">
				<section className="pos-orders-list">
					{loading && !list.length ? (
						<div className="pos-empty">Đang tải đơn hàng…</div>
					) : list.length ? (
						<div className="pos-order-grid">
							{list.map((o) => (
								<button
									type="button"
									key={o.name}
									className={`pos-order-card ${selected === o.name ? "is-active" : ""}`}
									onClick={() => setSelected(o.name)}
								>
									<div className="pos-order-card__top">
										<strong>{o.customer_name}</strong>
										<span className="pos-order-card__price">{formatMoney(o.amount, o.currency)}</span>
									</div>
									<div className="pos-order-card__meta">
										<span>{o.name}</span>
										<span className="pos-tag">{typeLabel(o.order_type)}</span>
										{o.buzzer_number ? <span className="pos-tag">Thẻ #{o.buzzer_number}</span> : null}
										{o.payment_status === "Đang chờ" ? <span className="pos-tag pos-tag--warn">Chờ QR</span> : null}
										{o.custom_kitchen_status ? <span className="pos-status__badge">{o.custom_kitchen_status}</span> : null}
										<span className="pos-order-card__time">{timeLabel(o.creation)}</span>
									</div>
								</button>
							))}
						</div>
					) : (
						<div className="pos-empty">
							{search ? "Không tìm thấy đơn phù hợp." : tab === "draft" ? "Không có đơn nào chờ thanh toán." : "Chưa có đơn đã thanh toán."}
						</div>
					)}
				</section>

				<aside className="pos-order-detail">
					{detail ? (
						<>
							<div className="pos-order-detail__head">
								<div>
									<div className="pos-order-detail__name">{detail.customer_name}</div>
									<div className="pos-order-detail__sub">
										{detail.name} · {typeLabel(detail.order_type)}
										{detail.order_type === "Dine In" ? ` · Thẻ #${detail.buzzer_number || "—"}` : ""}
									</div>
								</div>
								<span className={isDraft ? "pos-pending" : "pos-ok"}>
									{isDraft ? "Chờ thanh toán" : detail.status || "Đã thanh toán"}
								</span>
							</div>

							<div className="pos-order-detail__items">
								{detail.items.map((it, i) => (
									<div key={`${it.item_code}-${i}`} className="pos-detail__row pos-detail__row--item">
										<div className="pos-detail__item-main">
											<span>{it.item_name}</span>
											{it.sugar_level || it.ice_level ? (
												<small className="pos-detail__opts">
													Đường {it.sugar_level || 100}% · Đá {it.ice_level || 100}%
												</small>
											) : null}
										</div>
										<span>x{it.qty}</span>
										<strong>{formatMoney(it.amount, detail.currency)}</strong>
									</div>
								))}
							</div>

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

							<div className="pos-order-detail__actions">
								{isDraft ? (
									<>
										<button type="button" className="pos-btn pos-btn--primary" disabled={busy} onClick={payCash}>
											Thu tiền mặt
										</button>
										<button type="button" className="pos-btn" disabled={busy} onClick={genQr}>
											Thanh toán QR
										</button>
										<button type="button" className="pos-btn pos-btn--danger" disabled={busy} onClick={() => setConfirmCancel(true)}>
											Hủy đơn
										</button>
									</>
								) : null}
								{detail.order_type === "Dine In" &&
								detail.status === "Paid" &&
								detail.custom_kitchen_status === "Đã hoàn thành" ? (
									<button type="button" className="pos-btn pos-btn--success" disabled={busy} onClick={pickup}>
										Xác nhận khách đã lấy
									</button>
								) : null}
								<button type="button" className="pos-btn" disabled={busy} onClick={() => setPrinting(true)}>
									In
								</button>
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
								Đơn sẽ bị xóa hẳn và không khôi phục được.
								{detail.order_type === "Dine In" ? " Thẻ rung sẽ được trả về." : ""}
							</p>
							{waitingQr ? (
								<div className="pos-alert pos-alert--error">
									Đơn đang chờ thanh toán QR. Hãy chắc chắn khách chưa chuyển tiền.
								</div>
							) : null}
							<div className="pos-confirm__actions">
								<button type="button" className="pos-btn" onClick={() => setConfirmCancel(false)}>
									Giữ đơn
								</button>
								<button type="button" className="pos-btn pos-btn--danger-solid" disabled={busy} onClick={cancelOrder}>
									{busy ? "Đang hủy…" : "Hủy đơn"}
								</button>
							</div>
						</div>
					</div>
				</div>
			) : null}

			<QrModal qr={qr} onClose={() => setQr(null)} />
			<ReceiptModal order={printing ? detail : null} kind="customer" onClose={() => setPrinting(false)} />
		</div>
	);
}