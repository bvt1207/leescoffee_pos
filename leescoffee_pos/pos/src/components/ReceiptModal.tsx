import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { usePos } from "../lib/pos-context";
import { printWithPage } from "../lib/print";
import { formatMoney } from "../store/cart";
import type { OrderDetail } from "../types";

interface Props {
	order: OrderDetail | null;
	/** Bắt buộc in: không có ×/Đóng, không đóng bằng Esc hay bấm nền. */
	forced?: boolean;
	onClose: () => void;
}

const RECEIPT_PAGE = "80mm auto";
const DONE_MS = 2000;

const typeLabel = (t: string) => (t === "Take Away" ? "Mang đi" : "Tại quán");

// "2026-10-31 14:05:12.123" -> "14:05 31/10/2026"
function formatStamp(iso: string): string {
	const s = String(iso || "");
	if (s.length < 16) return s;
	const [y, m, d] = s.slice(0, 10).split("-");
	return `${s.slice(11, 16)} ${d}/${m}/${y}`;
}

function nowStamp(): string {
	const n = new Date();
	const p = (v: number) => String(v).padStart(2, "0");
	return `${p(n.getHours())}:${p(n.getMinutes())} ${p(n.getDate())}/${p(n.getMonth() + 1)}/${n.getFullYear()}`;
}

const itemTitle = (name: string, size?: string) => (size ? `${name} (${size})` : name);
const optsLabel = (sugar?: string, ice?: string) => `Đường ${sugar || 100}% · Đá ${ice || 100}%`;

export default function ReceiptModal({ order, forced = false, onClose }: Props) {
	const { config } = usePos();
	const [attempted, setAttempted] = useState(false);
	const [done, setDone] = useState(false);
	const [confirmSkip, setConfirmSkip] = useState(false);

	// Đơn khác -> bắt đầu lại
	useEffect(() => {
		setAttempted(false);
		setDone(false);
		setConfirmSkip(false);
	}, [order?.name]);

	useEffect(() => {
		if (!order || forced) return;
		const handler = (event: KeyboardEvent) => {
			if (event.key === "Escape") onClose();
		};
		window.addEventListener("keydown", handler);
		return () => window.removeEventListener("keydown", handler);
	}, [order, forced, onClose]);

	// In xong (bắt buộc): báo thành công ~2 giây rồi tự đóng
	useEffect(() => {
		if (!done) return;
		const t = window.setTimeout(onClose, DONE_MS);
		return () => window.clearTimeout(t);
	}, [done, onClose]);

	if (!order) return null;

	const brand = config?.brand;
	const isDraft = order.docstatus === 0;
	const modeLabel = (mode: string) =>
		config?.payment_modes.find((m) => m.name === mode)?.label || mode;
	const paidRows = order.payments.filter((p) => p.amount > 0);

	const doPrint = () => {
		setAttempted(true);
		setConfirmSkip(false);
		printWithPage(RECEIPT_PAGE, {
			onAfter: () => {
				if (forced) setDone(true);
			},
		});
	};

	const onBackdrop = () => {
		if (!forced) onClose();
	};

	let actions;
	if (done) {
		actions = (
			<div className="pos-receipt-done pos-no-print" role="status">
				Đã in hóa đơn thành công
			</div>
		);
	} else if (confirmSkip) {
		actions = (
			<div className="pos-receipt-skip pos-no-print">
				<p>Đơn đã thanh toán nhưng chưa in hóa đơn. Bỏ qua?</p>
				<div className="pos-receipt-actions">
					<button type="button" className="pos-btn" onClick={() => setConfirmSkip(false)}>
						Quay lại
					</button>
					<button type="button" className="pos-btn pos-btn--danger" onClick={onClose}>
						Bỏ qua
					</button>
				</div>
			</div>
		);
	} else {
		actions = (
			<div className="pos-receipt-actions pos-no-print">
				{forced ? (
					attempted ? (
						<button type="button" className="pos-btn pos-btn--ghost" onClick={() => setConfirmSkip(true)}>
							Bỏ qua in
						</button>
					) : null
				) : (
					<button type="button" className="pos-btn" onClick={onClose}>
						Đóng
					</button>
				)}
				<button type="button" className="pos-btn pos-btn--primary" onClick={doPrint}>
					In
				</button>
			</div>
		);
	}

	return createPortal(
		<div className="pos-modal-backdrop pos-modal-backdrop--receipt" onClick={onBackdrop}>
			<div
				className="pos-modal pos-modal--receipt"
				role="dialog"
				aria-modal="true"
				onClick={(event) => event.stopPropagation()}
			>
				<div className="pos-modal__header pos-no-print">
					<h3>{forced ? "In hóa đơn cho khách" : "In lại hóa đơn"}</h3>
					{!forced ? (
						<button type="button" className="pos-modal__close" aria-label="Đóng" onClick={onClose}>
							×
						</button>
					) : null}
				</div>

				<div className="pos-modal__body pos-receipt-body">
					<div className="pos-receipt">
						{brand ? (
							<div className="pos-receipt__brand">
								{brand.logo ? (
									<img className="pos-receipt__logo" src={brand.logo} alt={brand.name || "Logo"} />
								) : null}
								{brand.name ? <div className="pos-receipt__brand-name">{brand.name}</div> : null}
								{brand.address ? <div>{brand.address}</div> : null}
								{brand.phone ? <div>ĐT: {brand.phone}</div> : null}
							</div>
						) : null}

						<div className="pos-receipt__title">{isDraft ? "HÓA ĐƠN TẠM TÍNH" : "HÓA ĐƠN"}</div>

						<div className="pos-receipt__row">
							<span>Mã đơn</span>
							<strong>{order.name}</strong>
						</div>
						<div className="pos-receipt__row">
							<span>Giờ</span>
							<span>{formatStamp(order.creation)}</span>
						</div>
						<div className="pos-receipt__row">
							<span>Khách</span>
							<span>{order.customer_name}</span>
						</div>
						<div className="pos-receipt__row">
							<span>Loại đơn</span>
							<strong>{typeLabel(order.order_type)}</strong>
						</div>
						{order.order_type === "Dine In" ? (
							<div className="pos-receipt__row">
								<span>Thẻ rung</span>
								<strong>#{order.buzzer_number || "—"}</strong>
							</div>
						) : null}

						<hr className="pos-receipt__sep" />

						{order.items.map((it, i) => (
							<div key={`${it.item_code}-${i}`} className="pos-receipt__item">
								<div className="pos-receipt__item-name">{itemTitle(it.item_name, it.size)}</div>
								<div className="pos-receipt__opts">{optsLabel(it.sugar_level, it.ice_level)}</div>
								<div className="pos-receipt__row">
									<span>
										{it.qty} × {formatMoney(it.rate, "")}
									</span>
									<span>{formatMoney(it.amount, "")}</span>
								</div>
							</div>
						))}

						{order.order_note ? (
							<>
								<hr className="pos-receipt__sep" />
								<div className="pos-receipt__note">
									<strong>Ghi chú:</strong> {order.order_note}
								</div>
							</>
						) : null}

						<hr className="pos-receipt__sep" />
						<div className="pos-receipt__row pos-receipt__total">
							<span>Tổng cộng</span>
							<span>{formatMoney(order.amount, order.currency)}</span>
						</div>
						<div className="pos-receipt__row">
							<span>Thanh toán</span>
							<span>
								{isDraft || !paidRows.length
									? "Chưa thanh toán"
									: paidRows.map((p) => modeLabel(p.mode_of_payment)).join(", ")}
							</span>
						</div>

						<hr className="pos-receipt__sep" />
						<div className="pos-receipt__foot">In lúc {nowStamp()}</div>
					</div>
				</div>

				{actions}
			</div>
		</div>,
		document.body
	);
}
