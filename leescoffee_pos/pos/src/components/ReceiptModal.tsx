import { useEffect } from "react";
import { createPortal } from "react-dom";
import { usePos } from "../lib/pos-context";
import { formatMoney } from "../store/cart";
import type { OrderDetail } from "../types";

export type ReceiptKind = "customer" | "kitchen";

interface Props {
	order: OrderDetail | null;
	kind: ReceiptKind;
	onClose: () => void;
}

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

export default function ReceiptModal({ order, kind, onClose }: Props) {
	const { config } = usePos();

	useEffect(() => {
		if (!order) return;
		const handler = (event: KeyboardEvent) => {
			if (event.key === "Escape") onClose();
		};
		window.addEventListener("keydown", handler);
		return () => window.removeEventListener("keydown", handler);
	}, [order, onClose]);

	if (!order) return null;

	const brand = config?.brand;
	const isDraft = order.docstatus === 0;
	const isKitchen = kind === "kitchen";
	const modeLabel = (mode: string) =>
		config?.payment_modes.find((m) => m.name === mode)?.label || mode;
	const paidRows = order.payments.filter((p) => p.amount > 0);

	const title = isKitchen ? "PHIẾU PHA CHẾ" : isDraft ? "HÓA ĐƠN TẠM TÍNH" : "HÓA ĐƠN";

	return createPortal(
		<div className="pos-modal-backdrop pos-modal-backdrop--receipt" onClick={onClose}>
			<div
				className="pos-modal pos-modal--receipt"
				role="dialog"
				aria-modal="true"
				onClick={(event) => event.stopPropagation()}
			>
				<div className="pos-modal__header pos-no-print">
					<h3>{isKitchen ? "In phiếu pha chế" : "In hóa đơn"}</h3>
					<button type="button" className="pos-modal__close" aria-label="Đóng" onClick={onClose}>
						×
					</button>
				</div>

				<div className="pos-modal__body pos-receipt-body">
					<div className={`pos-receipt ${isKitchen ? "pos-receipt--kitchen" : ""}`}>
						{!isKitchen && brand ? (
							<div className="pos-receipt__brand">
								{brand.logo ? (
									<img className="pos-receipt__logo" src={brand.logo} alt={brand.name || "Logo"} />
								) : null}
								{brand.name ? <div className="pos-receipt__brand-name">{brand.name}</div> : null}
								{brand.address ? <div>{brand.address}</div> : null}
								{brand.phone ? <div>ĐT: {brand.phone}</div> : null}
							</div>
						) : null}

						<div className="pos-receipt__title">{title}</div>

						<div className="pos-receipt__row">
							<span>Mã đơn</span>
							<strong>{order.name}</strong>
						</div>
						<div className="pos-receipt__row">
							<span>Giờ</span>
							<span>{formatStamp(order.creation)}</span>
						</div>
						{!isKitchen ? (
							<div className="pos-receipt__row">
								<span>Khách</span>
								<span>{order.customer_name}</span>
							</div>
						) : null}
						<div className="pos-receipt__row">
							<span>Loại đơn</span>
							<strong>{typeLabel(order.order_type)}</strong>
						</div>
						{order.order_type === "Dine In" ? (
							isKitchen ? (
								<div className="pos-receipt__buzzer">Thẻ #{order.buzzer_number || "—"}</div>
							) : (
								<div className="pos-receipt__row">
									<span>Thẻ rung</span>
									<strong>#{order.buzzer_number || "—"}</strong>
								</div>
							)
						) : null}

						<hr className="pos-receipt__sep" />

						{order.items.map((it, i) => (
							<div key={`${it.item_code}-${i}`} className="pos-receipt__item">
								<div className="pos-receipt__item-name">
									{isKitchen ? `${it.qty}× ` : ""}
									{itemTitle(it.item_name, it.size)}
								</div>
								<div className="pos-receipt__opts">{optsLabel(it.sugar_level, it.ice_level)}</div>
								{!isKitchen ? (
									<div className="pos-receipt__row">
										<span>
											{it.qty} × {formatMoney(it.rate, "")}
										</span>
										<span>{formatMoney(it.amount, "")}</span>
									</div>
								) : null}
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

						{!isKitchen ? (
							<>
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
							</>
						) : null}

						<hr className="pos-receipt__sep" />
						<div className="pos-receipt__foot">In lúc {nowStamp()}</div>
					</div>
				</div>

				<div className="pos-receipt-actions pos-no-print">
					<button type="button" className="pos-btn" onClick={onClose}>
						Đóng
					</button>
					<button type="button" className="pos-btn pos-btn--primary" onClick={() => window.print()}>
						In
					</button>
				</div>
			</div>
		</div>,
		document.body
	);
}
