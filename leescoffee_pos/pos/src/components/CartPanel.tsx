import { useEffect, useRef, useState } from "react";
import { useCart, cartLineKey, cartTotal, cartCount, formatMoney } from "../store/cart";
import { usePos } from "../lib/pos-context";
import { cartUnitSurcharge, formatCartOptions, isSelected, missingRequired, plusPrice, toggleOption, valueSurcharge } from "../lib/options";
import type { LoyaltyInfo, PricingPreview, PricingPreviewItem } from "../types";

interface Props {
	loyalty?: LoyaltyInfo | null;
	preview?: PricingPreview | null;
	previewError?: string;
	previewLoading?: boolean;
}

const hasPromo = (p?: PricingPreviewItem) =>
	!!p && !p.is_free_item && (p.discount_percentage > 0 || p.rate < p.price_list_rate);

const promoLabel = (p: PricingPreviewItem) => {
	const pct = p.discount_percentage > 0 ? `Giảm ${p.discount_percentage}%` : "Khuyến mãi";
	const titles = p.rules.map((r) => r.title).filter(Boolean).join(", ");
	return titles ? `${pct} · ${titles}` : pct;
};

export default function CartPanel({
	loyalty = null,
	preview = null,
	previewError = "",
	previewLoading = false,
}: Props) {
	const lines = useCart((state) => state.lines);
	const increment = useCart((state) => state.increment);
	const decrement = useCart((state) => state.decrement);
	const removeLine = useCart((state) => state.removeLine);
	const setLineOptions = useCart((state) => state.setLineOptions);
	const orderNote = useCart((state) => state.orderNote);
	const setOrderNote = useCart((state) => state.setOrderNote);
	const clear = useCart((state) => state.clear);
	const { config } = usePos();

	const currency = config?.profile?.currency || "VND";
	// Tổng tạm (chưa có preview): giá món + phụ thu ước tính từ menu. Số thật lấy từ preview.
	const total = cartTotal(lines) + lines.reduce((s, l) => s + cartUnitSurcharge(l.options, l.option_groups) * l.qty, 0);
	const count = cartCount(lines);

	// Đổi điểm Loyalty: mức tối đa và số tiền giảm lấy từ preview (server tính sau CTKM).
	const redeemPoints = useCart((state) => state.redeemPoints);
	const setRedeemPoints = useCart((state) => state.setRedeemPoints);
	const factor = loyalty?.conversion_factor ?? 0;
	const maxRedeem = preview?.max_redeem_points ?? 0;
	const canRedeem = !!loyalty?.enrolled && (loyalty.loyalty_points ?? 0) > 0 && lines.length > 0;

	// Dòng preview khớp dòng giỏ (cùng vị trí, cùng mã, cùng số lượng); dòng tặng nằm ngoài.
	const previewFor = (idx: number): PricingPreviewItem | undefined => {
		const p = preview?.items[idx];
		const line = lines[idx];
		return p && line && !p.is_free_item && p.item_code === line.item_code && p.qty === line.qty
			? p
			: undefined;
	};
	const freeItems = (preview?.items || []).filter((p) => p.is_free_item);

	// Chỉ mở chip tùy chọn của MỘT dòng; dòng vừa thêm tự mở, dòng khác hiện tóm tắt.
	const [expanded, setExpanded] = useState<string | null>(null);
	const prevCount = useRef(lines.length);
	useEffect(() => {
		if (lines.length > prevCount.current) {
			const last = lines[lines.length - 1];
			if (last?.option_groups?.length) setExpanded(cartLineKey(last));
		}
		prevCount.current = lines.length;
	}, [lines]);

	return (
		<aside className="pos-cart">
			<div className="pos-cart__header">
				<h2>Giỏ hàng</h2>
				<span className="pos-badge">{count} món</span>
			</div>

			<div className="pos-cart__lines">
				{!lines.length ? (
					<div className="pos-cart__empty">
						<strong>Giỏ hàng trống</strong>
						<span>Chọn món để bắt đầu tạo đơn</span>
					</div>
				) : (
					lines.map((line, idx) => {
						const key = cartLineKey(line);
						const groups = line.option_groups || [];
						const missing = missingRequired(line.options, groups);
						const isOpen = expanded === key;
						const summary = formatCartOptions(line.options, groups, true);
						const unitExtra = cartUnitSurcharge(line.options, groups);
						const pv = previewFor(idx);
						const promo = hasPromo(pv) ? pv : undefined;
						return (
							<div key={key} className={`pos-cart-line${missing.length ? " is-missing" : ""}`}>
								<div className="pos-cart-line__head">
									<div className="pos-cart-line__name">
										{line.item_name}
										{line.size ? (
											<span className="pos-cart-line__size">{line.size}</span>
										) : null}
									</div>
									<div className="pos-cart-line__price">
										{promo ? (
											<>
												<span className="pos-price-old">
													{formatMoney((promo.price_list_rate + unitExtra) * promo.qty, currency)}
												</span>
												{formatMoney((promo.rate + unitExtra) * promo.qty, currency)}
											</>
										) : (
											formatMoney((line.price + unitExtra) * line.qty, currency)
										)}
									</div>
									<button
										type="button"
										className="pos-cart-line__remove"
										title="Xoá món"
										aria-label="Xoá món"
										onClick={() => removeLine(key)}
									>
										×
									</button>
								</div>

								{promo ? <span className="pos-promo-chip">{promoLabel(promo)}</span> : null}

								<div className="pos-cart-line__body">
									{groups.length ? (
										<button
											type="button"
											className="pos-cart-line__summary"
											aria-expanded={isOpen}
											onClick={() => setExpanded(isOpen ? null : key)}
										>
											<span className="pos-cart-line__summary-text">
												{summary || "Chọn tùy chọn"}
											</span>
											<span className="pos-cart-line__summary-caret" aria-hidden>
												{isOpen ? "▴" : "▾"}
											</span>
										</button>
									) : (
										<span />
									)}

									<div className="pos-cart-line__qty">
										<button
											type="button"
											className="pos-step"
											aria-label="Giảm"
											onClick={() => decrement(key)}
										>
											−
										</button>
										<span className="pos-cart-line__qty-value">{line.qty}</span>
										<button
											type="button"
											className="pos-step"
											aria-label="Tăng"
											onClick={() => increment(key)}
										>
											+
										</button>
									</div>
								</div>

								{groups.length && isOpen ? (
									<div className="pos-optgroups">
										{groups.map((g) => (
											<div key={g.name} className="pos-optgroup">
												<span className="pos-optgroup__title">
													{g.title}
													{g.required ? <span className="pos-optgroup__req"> *</span> : null}
													{g.selection_type === "Chọn nhiều" ? (
														<span className="pos-optgroup__hint"> · chọn nhiều</span>
													) : null}
												</span>
												<div
													className="pos-optchips"
													role={g.selection_type === "Chọn 1" ? "radiogroup" : "group"}
													aria-label={g.title}
												>
													{g.values.map((v) => {
														const on = isSelected(line.options, g.name, v.label);
														return (
															<button
																type="button"
																key={v.label}
																className={`pos-optchip${on ? " is-active" : ""}`}
																role={g.selection_type === "Chọn 1" ? "radio" : "checkbox"}
																aria-checked={on}
																onClick={() =>
																	setExpanded(setLineOptions(key, toggleOption(line.options, g, v.label)))
																}
															>
																{v.label}
																{valueSurcharge(groups, g.name, v.label) > 0 ? (
																	<span className="pos-optchip__price">
																		{plusPrice(valueSurcharge(groups, g.name, v.label))}
																	</span>
																) : null}
															</button>
														);
													})}
												</div>
											</div>
										))}
									</div>
								) : null}

								{missing.length ? (
									<div className="pos-cart-line__missing">
										Chọn {missing.map((g) => g.title).join(", ")}
									</div>
								) : null}

								{line.note ? <div className="pos-cart-line__note">{line.note}</div> : null}
							</div>
						);
					})
				)}

				{lines.length
					? freeItems.map((p, i) => (
							<div key={`free-${p.item_code}-${i}`} className="pos-cart-line pos-cart-line--free">
								<div className="pos-cart-line__head">
									<div className="pos-cart-line__name">
										{p.item_code}
										<span className="pos-promo-chip">Tặng</span>
									</div>
									<div className="pos-cart-line__price">
										{p.qty} × {formatMoney(0, currency)}
									</div>
								</div>
							</div>
					  ))
					: null}
			</div>

			<div className="pos-cart__footer">
				<label className="pos-cart__note-label" htmlFor="pos-order-note">
					Ghi chú đơn hàng
				</label>
				<textarea
					id="pos-order-note"
					className="pos-input pos-textarea"
					placeholder="Ví dụ: ít ngọt, mang đi…"
					value={orderNote}
					onChange={(event) => setOrderNote(event.target.value)}
					rows={2}
				/>
				{canRedeem ? (
					<div className="pos-redeem">
						<div className="pos-redeem__info">
							<span className="pos-redeem__label">Dùng điểm</span>
							<small>
								Tối đa {maxRedeem} điểm · 1 điểm = {formatMoney(factor, currency)}
							</small>
						</div>
						<div className="pos-redeem__stepper">
							<button
								type="button"
								className="pos-step"
								aria-label="Bớt điểm"
								disabled={redeemPoints <= 0}
								onClick={() => setRedeemPoints(redeemPoints - 1)}
							>
								−
							</button>
							<span className="pos-redeem__value">{redeemPoints}</span>
							<button
								type="button"
								className="pos-step"
								aria-label="Thêm điểm"
								disabled={redeemPoints >= maxRedeem}
								onClick={() => setRedeemPoints(redeemPoints + 1)}
							>
								+
							</button>
						</div>
					</div>
				) : null}

				{preview && lines.length ? (
					<>
						<div className="pos-redeem__row">
							<span>Tạm tính</span>
							<span>{formatMoney(preview.total_before, currency)}</span>
						</div>
						{preview.total_discount_rules > 0 ? (
							<div className="pos-redeem__row pos-redeem__row--discount">
								<span>Khuyến mãi</span>
								<span>−{formatMoney(preview.total_discount_rules, currency)}</span>
							</div>
						) : null}
						{(preview.total_surcharge ?? 0) > 0 ? (
							<div className="pos-redeem__row">
								<span>Phụ thu topping</span>
								<span>+{formatMoney(preview.total_surcharge ?? 0, currency)}</span>
							</div>
						) : null}
						{preview.loyalty_discount > 0 ? (
							<div className="pos-redeem__row pos-redeem__row--discount">
								<span>Đổi điểm ({redeemPoints} điểm)</span>
								<span>−{formatMoney(preview.loyalty_discount, currency)}</span>
							</div>
						) : null}
						<div className="pos-cart__total">
							<span>Tổng cộng</span>
							<strong>{formatMoney(preview.grand_total, currency)}</strong>
						</div>
					</>
				) : (
					<div className="pos-cart__total">
						<span>{lines.length ? "Tổng cộng (chưa áp KM)" : "Tổng cộng"}</span>
						<strong>{formatMoney(total, currency)}</strong>
					</div>
				)}

				{lines.length && previewLoading ? (
					<div className="pos-cart__hint">Đang tính khuyến mãi…</div>
				) : null}
				{lines.length && previewError && !previewLoading ? (
					<div className="pos-cart__hint pos-cart__hint--error">
						Chưa tính được khuyến mãi: {previewError}
					</div>
				) : null}
				{lines.length ? (
					<button type="button" className="pos-btn pos-btn--ghost" onClick={() => clear()}>
						Xoá giỏ
					</button>
				) : null}
			</div>
		</aside>
	);
}