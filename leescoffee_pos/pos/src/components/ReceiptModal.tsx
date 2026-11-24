import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { isQrOrder, typeLabel } from "./OrderTypeChip";
import { formatOptions, lineUnitSurcharge } from "../lib/options";
import { usePos } from "../lib/pos-context";
import { customerLabel, formatStamp, nowStamp } from "../lib/format";
import { printWithPage } from "../lib/print";
import { formatMoney } from "../store/cart";
import type { OrderDetail } from "../types";

export type ReceiptKind = "customer" | "kitchen";

interface Props {
	order: OrderDetail | null;
	/** customer = hóa đơn khách; kitchen = phiếu pha chế tổng (không giá, không thương hiệu). */
	kind?: ReceiptKind;
	/** Bắt buộc in: không có ×/Đóng, không đóng bằng Esc hay bấm nền. */
	forced?: boolean;
	/** Gọi sau mỗi lần in (afterprint). */
	onPrinted?: () => void;
	onClose: () => void;
}

const RECEIPT_PAGE = "80mm auto";
const DONE_MS = 2000;


const itemTitle = (name: string, size?: string) => (size ? `${name} (${size})` : name);

// Món có CTKM: giá gốc (price_list_rate) cao hơn giá bán (rate) do server trả.
type Item = OrderDetail["items"][number];
const itemPromo = (it: Item) => (it.discount_percentage ?? 0) > 0 || (it.price_list_rate ?? 0) > it.rate;
const promoTotal = (items: Item[]) =>
	items.reduce((sum, it) => sum + (itemPromo(it) ? ((it.price_list_rate ?? 0) - it.rate) * it.qty : 0), 0);

export default function ReceiptModal({ order, kind = "customer", forced = false, onPrinted, onClose }: Props) {
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
	const isKitchen = kind === "kitchen";
	const title = isKitchen ? "PHIẾU PHA CHẾ" : isDraft ? "HÓA ĐƠN TẠM TÍNH" : "HÓA ĐƠN";
	const heading = isKitchen ? "In phiếu pha chế" : forced ? "In hóa đơn cho khách" : "In lại hóa đơn";
	const modeLabel = (mode: string) =>
		config?.payment_modes.find((m) => m.name === mode)?.label || mode;
	const paidRows = order.payments.filter((p) => p.amount > 0);

	const doPrint = () => {
		setAttempted(true);
		setConfirmSkip(false);
		printWithPage(RECEIPT_PAGE, {
			onAfter: () => {
				onPrinted?.();
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
					<h3>{heading}</h3>
					{!forced ? (
						<button type="button" className="pos-modal__close" aria-label="Đóng" onClick={onClose}>
							×
						</button>
					) : null}
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
								<span>{customerLabel(order)}</span>
							</div>
						) : null}
						<div className="pos-receipt__row">
							<span>Loại đơn</span>
							<strong>{typeLabel(order.order_type)}</strong>
						</div>
						{isQrOrder(order.order_channel) ? (
							<div className="pos-receipt__row">
								<span>Kênh</span>
								<strong>QR · {order.customer_name}</strong>
							</div>
						) : order.order_type === "Dine In" ? (
							isKitchen ? (
								<div className="pos-receipt__buzzer">Bàn #{order.buzzer_number || "—"}</div>
							) : (
								<div className="pos-receipt__row">
									<span>Thẻ bàn</span>
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
								{/* Phiếu pha chế: chỉ tên tùy chọn; hóa đơn khách: kèm phụ thu "(+10.000)". */}
								{formatOptions(it.options, !isKitchen) ? (
									<div className="pos-receipt__opts">{formatOptions(it.options, !isKitchen)}</div>
								) : null}
								{!isKitchen && itemPromo(it) ? (
									<div className="pos-receipt__opts">
										Giá gốc {formatMoney(it.price_list_rate ?? 0, "")}
										{(it.discount_percentage ?? 0) > 0 ? ` · KM −${it.discount_percentage}%` : " · KM"}
									</div>
								) : null}
								{!isKitchen ? (
									<div className="pos-receipt__row">
										<span>
											{it.qty} × {formatMoney(it.rate + lineUnitSurcharge(it.options), "")}
										</span>
										<span>{formatMoney(it.amount + lineUnitSurcharge(it.options) * it.qty, "")}</span>
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
								{promoTotal(order.items) > 0 ? (
									<div className="pos-receipt__row">
										<span>Khuyến mãi</span>
										<span>−{formatMoney(promoTotal(order.items), "")}</span>
									</div>
								) : null}
								{(order.total_surcharge ?? 0) > 0 ? (
									<div className="pos-receipt__row">
										<span>Gồm phụ thu topping</span>
										<span>{formatMoney(order.total_surcharge ?? 0, "")}</span>
									</div>
								) : null}
								{(order.discount_amount ?? 0) > 0 ? (
									<div className="pos-receipt__row">
										<span>
											Giảm giá đổi điểm
											{order.redeemed_points ? ` (${order.redeemed_points} điểm)` : ""}
										</span>
										<span>−{formatMoney(order.discount_amount ?? 0, "")}</span>
									</div>
								) : null}
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

				{actions}
			</div>
		</div>,
		document.body
	);
}
