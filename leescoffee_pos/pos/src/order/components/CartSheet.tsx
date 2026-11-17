import { useEffect, useMemo, useRef, useState } from "react";
import { cartUnitSurcharge, formatCartOptions } from "../../lib/options";
import { errorText, OrderApiError, orderApi } from "../api";
import { cartPayload, MAX_LINE_QTY, useOrderCart } from "../cart";
import { money } from "../format";
import type { Loyalty, OrderTypeValue, Preview } from "../types";
import OrderTypePicker from "./OrderTypePicker";
import Sheet from "./Sheet";

const PREVIEW_DEBOUNCE_MS = 350;

/**
 * Giỏ hàng + xem trước giá do SERVER tính (CTKM theo tổng qty mỗi mã, điểm/hạng).
 * Frontend chỉ hiển thị; tạo đơn gửi item_code/qty/options, server tính lại toàn bộ.
 */
export default function CartSheet({
	token,
	currency,
	orderType,
	isOpen,
	loyalty,
	onOrderType,
	onSessionExpired,
	onCheckout,
	onClose,
}: {
	token: string;
	currency: string;
	orderType: OrderTypeValue;
	isOpen: boolean;
	loyalty: Loyalty | null;
	onOrderType: (v: OrderTypeValue) => void;
	onSessionExpired: () => void;
	onCheckout: () => Promise<void>;
	onClose: () => void;
}) {
	const { lines, note, setQty, remove, setNote } = useOrderCart();
	const [preview, setPreview] = useState<Preview | null>(null);
	const [previewError, setPreviewError] = useState("");
	const [loading, setLoading] = useState(false);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState("");

	// Khóa chuỗi ổn định của đúng dữ liệu gửi server (item_code, qty, options). Ghi chú, ảnh, tên món
	// không nằm trong khóa -> gõ ghi chú hay mảng `lines` mới cùng nội dung KHÔNG gọi lại preview.
	// Loại đơn không gửi cho `preview` (server không tính theo loại đơn) nên cũng không nằm trong khóa.
	const itemsKey = useMemo(() => JSON.stringify(cartPayload(lines)), [lines]);
	const expiredRef = useRef(onSessionExpired);
	expiredRef.current = onSessionExpired;

	// Xem trước giá: debounce 350ms theo itemsKey; abort request cũ + chỉ nhận kết quả của lần gọi mới nhất.
	useEffect(() => {
		if (itemsKey === "[]" || !isOpen) {
			setPreview(null);
			setPreviewError("");
			setLoading(false);
			return;
		}
		const ctrl = new AbortController();
		setLoading(true);
		const t = window.setTimeout(async () => {
			try {
				const p = await orderApi.preview(token, JSON.parse(itemsKey), ctrl.signal);
				if (ctrl.signal.aborted) return;
				setPreview(p);
				setPreviewError("");
			} catch (err) {
				if (ctrl.signal.aborted || (err instanceof OrderApiError && err.aborted)) return;
				if (err instanceof OrderApiError && err.sessionExpired) return expiredRef.current();
				setPreview(null);
				setPreviewError(errorText(err));
			} finally {
				if (!ctrl.signal.aborted) setLoading(false);
			}
		}, PREVIEW_DEBOUNCE_MS);
		return () => {
			window.clearTimeout(t);
			ctrl.abort();
		};
	}, [itemsKey, token, isOpen]);

	const paid = preview ? preview.items.filter((p) => !p.is_free_item) : [];
	const gifts = preview ? preview.items.filter((p) => p.is_free_item) : [];
	// Tổng tạm khi chưa có preview: giá món + phụ thu ước tính từ menu (số thật do server tính).
	const fallbackTotal = lines.reduce((s, l) => s + (l.rate + cartUnitSurcharge(l.options, l.option_groups)) * l.qty, 0);
	const pts = (preview?.loyalty || loyalty) as Loyalty | null;

	const checkout = async () => {
		if (busy) return;
		setBusy(true);
		setError("");
		try {
			await onCheckout();
		} catch (err) {
			if (err instanceof OrderApiError && err.sessionExpired) return onSessionExpired();
			setError(errorText(err));
		} finally {
			setBusy(false);
		}
	};

	const footer = (
		<div className="qo-checkout">
			<div className="qo-checkout__total">
				<span>Tổng thanh toán</span>
				<strong aria-live="polite">
					{loading ? "Đang tính…" : money(preview ? preview.grand_total : fallbackTotal, currency)}
				</strong>
			</div>
			{error ? (
				<div className="qo-alert qo-alert--error" role="alert">
					{error}
				</div>
			) : null}
			<button
				type="button"
				className="qo-btn qo-btn--primary qo-btn--block"
				disabled={!lines.length || !isOpen || busy || loading || !!previewError}
				onClick={checkout}
			>
				{!isOpen ? "Quán chưa mở bán" : busy ? "Đang tạo đơn…" : "Đặt món & chuyển khoản"}
			</button>
		</div>
	);

	return (
		<Sheet title="Giỏ hàng" onClose={onClose} footer={lines.length ? footer : undefined} labelledBy="qo-cart-title">
			{!lines.length ? (
				<div className="qo-empty">Giỏ hàng trống. Chọn món để bắt đầu.</div>
			) : (
				<>
					<div className="qo-cart__type">
						<span className="qo-cart__label">Loại đơn</span>
						<OrderTypePicker variant="segmented" value={orderType} onChange={onOrderType} />
					</div>

					<ul className="qo-lines">
						{lines.map((l, i) => {
							const p = paid[i] && paid[i].item_code === l.item_code ? paid[i] : null;
							const discounted = p && p.rate < p.price_list_rate;
							const opts = formatCartOptions(l.options, l.option_groups, true);
							const unitExtra = cartUnitSurcharge(l.options, l.option_groups);
							return (
								<li key={l.key} className="qo-line">
									<div className="qo-line__main">
										<div className="qo-line__name">
											{l.item_name}
											{l.size_label ? <span className="qo-line__size"> · {l.size_label}</span> : null}
										</div>
										{opts ? <div className="qo-line__opts">{opts}</div> : null}
										{p && p.rules.length ? (
											<div className="qo-line__promo">{p.rules.map((r) => r.title).join(", ")}</div>
										) : null}
										<div className="qo-line__price">
											{discounted ? (
												<s className="qo-line__was">{money((p.price_list_rate + unitExtra) * l.qty, currency)}</s>
											) : null}
											<span>{money(((p ? p.rate : l.rate) + unitExtra) * l.qty, currency)}</span>
										</div>
									</div>
									<div className="qo-stepper qo-stepper--sm">
										<button
											type="button"
											className="qo-stepper__btn"
											aria-label={l.qty <= 1 ? `Xóa ${l.item_name}` : `Bớt 1 ${l.item_name}`}
											onClick={() => (l.qty <= 1 ? remove(l.key) : setQty(l.key, l.qty - 1))}
										>
											{l.qty <= 1 ? "×" : "−"}
										</button>
										<span className="qo-stepper__val">{l.qty}</span>
										<button
											type="button"
											className="qo-stepper__btn"
											aria-label={`Thêm 1 ${l.item_name}`}
											disabled={l.qty >= MAX_LINE_QTY}
											onClick={() => setQty(l.key, l.qty + 1)}
										>
											+
										</button>
									</div>
								</li>
							);
						})}
					</ul>

					{gifts.length ? (
						<div className="qo-gifts">
							<span className="qo-cart__label">Quà tặng kèm</span>
							{gifts.map((g, i) => (
								<div key={`${g.item_code}-${i}`} className="qo-gifts__row">
									{g.qty}× {g.item_code}
								</div>
							))}
						</div>
					) : null}

					<label className="qo-field">
						<span className="qo-field__label">Ghi chú cho quán</span>
						<textarea
							className="qo-input qo-textarea"
							rows={2}
							maxLength={200}
							placeholder="Ví dụ: ít ngọt, giao chung một lần"
							value={note}
							onChange={(e) => setNote(e.target.value)}
						/>
					</label>

					<div className="qo-summary">
						{preview && preview.total_discount_rules > 0 ? (
							<>
								<div className="qo-summary__row">
									<span>Tạm tính</span>
									<span>{money(preview.total_before, currency)}</span>
								</div>
								<div className="qo-summary__row qo-summary__row--save">
									<span>Khuyến mãi</span>
									<span>−{money(preview.total_discount_rules, currency)}</span>
								</div>
							</>
						) : null}
						{preview && (preview.total_surcharge ?? 0) > 0 ? (
							<div className="qo-summary__row">
								<span>Phụ thu topping</span>
								<span>+{money(preview.total_surcharge ?? 0, currency)}</span>
							</div>
						) : null}
						{previewError ? (
							<div className="qo-alert qo-alert--error" role="alert">
								{previewError}
							</div>
						) : null}
					</div>

					{pts?.enrolled ? (
						<div className="qo-points">
							<strong>
								{pts.tier_name ? `${pts.tier_name} · ` : ""}
								{pts.loyalty_points ?? 0} điểm
							</strong>
							<span>Đơn này được tích điểm. Đổi điểm hiện chỉ làm tại quầy.</span>
						</div>
					) : null}

					<p className="qo-fine">Thanh toán bằng chuyển khoản qua mã QR ngay sau khi đặt.</p>
				</>
			)}
		</Sheet>
	);
}
