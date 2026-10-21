import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import QrModal from "../components/QrModal";
import { api } from "../lib/api";
import { formatMoney } from "../store/cart";
import type { OrderDetail, OrderSummary, QrInfo, StatusBoardRow } from "../types";

export default function Orders() {
	const navigate = useNavigate();
	const [params] = useSearchParams();
	const draftParam = params.get("draft");

	const [drafts, setDrafts] = useState<OrderSummary[]>([]);
	const [paid, setPaid] = useState<OrderSummary[]>([]);
	const [board, setBoard] = useState<StatusBoardRow[]>([]);
	const [selected, setSelected] = useState<string | null>(draftParam || null);
	const [detail, setDetail] = useState<OrderDetail | null>(null);
	const [qr, setQr] = useState<QrInfo | null>(null);
	const [busy, setBusy] = useState(false);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");

	const loadDetail = useCallback(async (invoiceName: string | null) => {
		if (!invoiceName) {
			setDetail(null);
			return;
		}
		try {
			const data = await api.getOrderDetail(invoiceName);
			setDetail(data);
		} catch {
			setDetail(null);
		}
	}, []);

	const loadData = useCallback(async () => {
		setLoading(true);
		try {
			const [d, p, b] = await Promise.all([
				api.getOrders("draft"),
				api.getOrders("paid"),
				api.getStatusBoard(),
			]);
			setDrafts(d || []);
			setPaid(p || []);
			setBoard(b || []);
			setError("");
		} catch (err) {
			setError(err instanceof Error ? err.message : String(err));
		} finally {
			setLoading(false);
		}
	}, []);

	// Tải danh sách đơn + bảng trạng thái, tự làm mới mỗi 10 giây.
	useEffect(() => {
		loadData();
		const timer = window.setInterval(loadData, 10000);
		return () => window.clearInterval(timer);
	}, [loadData]);

	// Chi tiết đơn đang chọn — tự làm mới theo nhịp lấy danh sách.
	useEffect(() => {
		loadDetail(selected);
		const timer = window.setInterval(() => loadDetail(selected), 10000);
		return () => window.clearInterval(timer);
	}, [selected, loadDetail]);

	useEffect(() => {
		if (draftParam) setSelected(draftParam);
	}, [draftParam]);

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

	const handlePayCash = () =>
		run(async () => {
			if (!detail) return;
			await api.payCash(detail.name);
			await loadData();
			await loadDetail(detail.name);
		});

	const handleGenerateQr = () =>
		run(async () => {
			if (!detail) return;
			const result = await api.generateQr(detail.name);
			setQr(result);
			await loadData();
			await loadDetail(detail.name);
		});

	const handleConfirmPickup = () =>
		run(async () => {
			if (!detail) return;
			await api.confirmPickup(detail.name);
			await loadData();
			await loadDetail(detail.name);
		});

	const pending = drafts.filter((order) => order.docstatus === 0);

	return (
		<div className="pos-page">
			{error ? <div className="pos-alert pos-alert--error">{error}</div> : null}

			<div className="pos-orders">
				<section className="pos-panel">
					<h2 className="pos-panel__title">Chờ thanh toán ({pending.length})</h2>
					{loading && !pending.length ? (
						<div className="pos-empty">Đang tải đơn hàng…</div>
					) : null}
					{!loading && !pending.length ? (
						<div className="pos-empty">Không có đơn nào chờ thanh toán.</div>
					) : null}
					<ul className="pos-list">
						{pending.map((order) => (
							<li key={order.name}>
								<button
									type="button"
									className={`pos-item ${selected === order.name ? "is-active" : ""}`}
									onClick={() => setSelected(order.name)}
								>
									<span className="pos-item__line">
										<span className="pos-item__name">{order.customer_name}</span>
										<span className="pos-tag">
											{order.order_type === "Take Away" ? "Mang đi" : "Tại quầy"}
										</span>
										<span className="pos-item__code">{order.name}</span>
									</span>
									<span className="pos-item__right">
										<strong>{formatMoney(order.amount, order.currency)}</strong>
									</span>
								</button>
							</li>
						))}
					</ul>
				</section>

				<section className="pos-panel">
					<h2 className="pos-panel__title">Chi tiết đơn</h2>
					{detail ? (
						<>
							<dl className="pos-detail">
								<dt>Khách</dt>
								<dd>{detail.customer_name}</dd>

								<dt>Loại đơn</dt>
								<dd>{detail.order_type === "Take Away" ? "Mang đi" : "Tại quầy"}</dd>

								<dt>Món</dt>
								<dd>
									{detail.items.map((item) => (
										<div key={item.item_code} className="pos-detail__row">
											<span>{item.item_name}</span>
											<span>x{item.qty}</span>
											<strong>{formatMoney(item.amount, detail.currency)}</strong>
										</div>
									))}
								</dd>

								<dt>Tổng cộng</dt>
								<dd>
									<strong>{formatMoney(detail.grand_total, detail.currency)}</strong>
								</dd>

								<dt>Trạng thái</dt>
								<dd>
									{detail.docstatus ? (
										<span className="pos-ok">{detail.status || "Đã thanh toán"}</span>
									) : (
										<span className="pos-pending">Draft</span>
									)}
								</dd>

								{detail.payment_status ? (
									<>
										<dt>Thanh toán</dt>
										<dd>{detail.payment_status}</dd>
									</>
								) : null}

								{detail.custom_kitchen_status ? (
									<>
										<dt>Bếp</dt>
										<dd>{detail.custom_kitchen_status}</dd>
									</>
								) : null}

								{detail.order_type === "Dine In" ? (
									<>
										<dt>Thẻ rung</dt>
										<dd>#{detail.buzzer_number || "—"}</dd>
									</>
								) : null}
							</dl>

							<div className="pos-actions">
								{detail.docstatus === 0 ? (
									<button
										type="button"
										className="pos-btn pos-btn--primary"
										disabled={busy}
										onClick={handlePayCash}
									>
										Thu tiền tại quầy
									</button>
								) : null}

								{detail.docstatus === 0 ? (
									<button
										type="button"
										className="pos-btn"
										disabled={busy}
										onClick={handleGenerateQr}
									>
										Thanh toán QR
									</button>
								) : null}

								{detail.order_type === "Dine In" &&
								detail.status === "Paid" &&
								detail.custom_kitchen_status === "Đã hoàn thành" ? (
									<button
										type="button"
										className="pos-btn pos-btn--success"
										disabled={busy}
										onClick={handleConfirmPickup}
									>
										Xác nhận khách đã lấy
									</button>
								) : null}
							</div>
						</>
					) : (
						<div className="pos-empty">Chọn một đơn ở danh sách bên trái.</div>
					)}
				</section>
			</div>

			<section className="pos-panel">
				<h2 className="pos-panel__title">Đã thanh toán ({paid.length})</h2>
				{!paid.length ? <div className="pos-empty">Chưa có đơn đã thanh toán.</div> : null}
				<ul className="pos-list">
					{paid.map((order) => (
						<li key={order.name}>
							<button
								type="button"
								className={`pos-item ${selected === order.name ? "is-active" : ""}`}
								onClick={() => setSelected(order.name)}
							>
								<span className="pos-item__line">
									<span className="pos-item__name">{order.customer_name}</span>
									<span className="pos-tag">
										{order.order_type === "Take Away" ? "Mang đi" : "Tại quầy"}
									</span>
									{order.custom_kitchen_status ? (
										<span className="pos-status__badge">{order.custom_kitchen_status}</span>
									) : null}
									{order.buzzer_number ? (
										<span className="pos-status__buzzer">Thẻ #{order.buzzer_number}</span>
									) : null}
								</span>
								<span className="pos-item__right">
									<strong>{formatMoney(order.amount, order.currency)}</strong>
								</span>
							</button>
						</li>
					))}
				</ul>
			</section>

			{board.length ? (
				<section className="pos-panel">
					<h2 className="pos-panel__title">Trạng thái bếp</h2>
					<ul className="pos-list">
						{board.map((row) => (
							<li key={row.invoice_name}>
								<span className="pos-item__line">
									<span className="pos-item__name">{row.customer_name}</span>
									<span className="pos-tag">
										{row.order_type === "Take Away" ? "Mang đi" : "Tại quầy"}
									</span>
									<span className="pos-status__badge">{row.kitchen_status}</span>
									{row.buzzer_number ? (
										<span className="pos-status__buzzer">Thẻ rung #{row.buzzer_number}</span>
									) : null}
								</span>
							</li>
						))}
					</ul>
				</section>
			) : null}

			<QrModal qr={qr} onClose={() => setQr(null)} />

			<div className="pos-pager">
				<button type="button" onClick={() => navigate("/")}>
					← Quay lại bán hàng
				</button>
			</div>
		</div>
	);
}
