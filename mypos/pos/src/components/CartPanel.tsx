import { useEffect, useRef, useState, type ReactNode } from "react";
import { useCart, cartLineKey, cartTotal, cartCount, formatMoney, MAX_LINE_QTY } from "../store/cart";
import { usePos } from "../lib/pos-context";
import { cartUnitSurcharge, formatCartOptions, missingRequired } from "../lib/options";
import OptionChips from "./OptionChips";
import type { LoyaltyInfo, PricingPreview, PricingPreviewItem } from "../types";

interface Props {
	loyalty?: LoyaltyInfo | null;
	preview?: PricingPreview | null;
	previewError?: string;
	previewLoading?: boolean;
	/** Phần cuối chân giỏ (cảnh báo + nút Tạo đơn) do trang POS truyền vào, luôn hiện, không cuộn. */
	children?: ReactNode;
}

const hasPromo = (p?: PricingPreviewItem) =>
	!!p && !p.is_free_item && (p.discount_percentage > 0 || p.rate < p.price_list_rate);

/** Tên chương trình (Pricing Rule title) của dòng preview, không trùng, giữ thứ tự server trả. */
const ruleTitles = (p: PricingPreviewItem) =>
	Array.from(new Set((p.rules || []).map((r) => r.title || r.name).filter(Boolean)));

const promoLabel = (p: PricingPreviewItem) => {
	const pct = p.discount_percentage > 0 ? `Giảm ${p.discount_percentage}%` : "Khuyến mãi";
	const titles = ruleTitles(p).join(", ");
	return titles ? `${pct} · ${titles}` : pct;
};

/**
 * Chip CTKM hiện sẵn dưới tóm tắt tùy chọn: "Giảm 5% · {luật đầu}" + "+N" nếu nhiều luật.
 * Số liệu lấy nguyên từ preview_pricing (không tính lại); title của chip = nhãn đầy đủ.
 */
function PromoChip({ prefix, titles, full }: { prefix: string; titles: string[]; full: string }) {
	return (
		<span className="pos-promo-chip pos-promo-chip--line" title={full}>
			<span className="pos-promo-chip__text">{titles[0] ? `${prefix} · ${titles[0]}` : prefix}</span>
			{titles.length > 1 ? <span className="pos-promo-chip__more">+{titles.length - 1}</span> : null}
		</span>
	);
}

/**
 * Ô số lượng gõ trực tiếp giữa −/+. Khi đang gõ chỉ giữ bản nháp cục bộ (không ghi store -> không gọi
 * preview_pricing). Enter / rời ô: số nguyên >= 1 thì áp dụng (vượt MAX_LINE_QTY thì cắt + báo nhẹ);
 * rỗng, 0, chữ, số âm -> quay về số cũ, không xóa dòng. Esc -> hủy, giữ số cũ.
 */
function QtyInput({ value, onCommit }: { value: number; onCommit: (qty: number) => void }) {
	const [draft, setDraft] = useState<string | null>(null);
	const [note, setNote] = useState("");
	const cancelRef = useRef(false);

	useEffect(() => {
		if (!note) return;
		const timer = window.setTimeout(() => setNote(""), 2500);
		return () => window.clearTimeout(timer);
	}, [note]);

	const apply = (raw: string) => {
		const text = raw.trim();
		if (!/^\d+$/.test(text)) {
			if (text) setNote("Chỉ nhập số nguyên từ 1");
			return;
		}
		const n = parseInt(text, 10);
		if (n < 1) return;
		if (n > MAX_LINE_QTY) {
			setNote(`Tối đa ${MAX_LINE_QTY}`);
			onCommit(MAX_LINE_QTY);
			return;
		}
		if (n !== value) onCommit(n);
	};

	return (
		<span className="pos-qty">
			<input
				type="text"
				inputMode="numeric"
				className="pos-qty__input"
				aria-label="Số lượng"
				maxLength={6}
				value={draft ?? String(value)}
				onFocus={(event) => {
					cancelRef.current = false;
					setDraft(String(value));
					event.currentTarget.select();
				}}
				onChange={(event) => setDraft(event.target.value)}
				onKeyDown={(event) => {
					if (event.key === "Enter") {
						event.currentTarget.blur();
					} else if (event.key === "Escape") {
						event.stopPropagation();
						cancelRef.current = true;
						event.currentTarget.blur();
					}
				}}
				onBlur={(event) => {
					const raw = event.currentTarget.value;
					setDraft(null);
					if (cancelRef.current) {
						cancelRef.current = false;
						return;
					}
					apply(raw);
				}}
			/>
			{note ? (
				<span className="pos-qty__note" role="status">
					{note}
				</span>
			) : null}
		</span>
	);
}

export default function CartPanel({
	loyalty = null,
	preview = null,
	previewError = "",
	previewLoading = false,
	children,
}: Props) {
	const lines = useCart((state) => state.lines);
	const increment = useCart((state) => state.increment);
	const decrement = useCart((state) => state.decrement);
	const setQty = useCart((state) => state.setQty);
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
	// Tên các chương trình đang áp dụng cho đơn (mọi dòng preview, kể cả dòng tặng), không trùng.
	const promoNames = lines.length
		? Array.from(new Set((preview?.items || []).flatMap((p) => ruleTitles(p)))).join(", ")
		: "";

	// Chỉ mở chip tùy chọn của MỘT dòng. Món vừa thêm: mở nếu có nhóm tùy chọn, không thì thu dòng đang mở.
	const [expanded, setExpanded] = useState<string | null>(null);
	const prevCount = useRef(lines.length);
	useEffect(() => {
		if (lines.length > prevCount.current) {
			const last = lines[lines.length - 1];
			setExpanded(last?.option_groups?.length ? cartLineKey(last) : null);
		}
		prevCount.current = lines.length;
	}, [lines]);

	// Bấm ra ngoài dòng đang mở -> thu lại.
	const openRef = useRef<HTMLDivElement | null>(null);
	useEffect(() => {
		if (!expanded) return;
		const onDown = (event: PointerEvent) => {
			const el = openRef.current;
			if (el && !el.contains(event.target as Node)) setExpanded(null);
		};
		document.addEventListener("pointerdown", onDown);
		return () => document.removeEventListener("pointerdown", onDown);
	}, [expanded]);

	// Ghi chú đơn và khối đổi điểm gập mặc định.
	const [noteOpen, setNoteOpen] = useState(false);
	const [redeemOpen, setRedeemOpen] = useState(false);

	return (
		<aside className="pos-cart">
			<div className="pos-cart__header">
				<h2>Giỏ hàng</h2>
				<span className="pos-badge">{count} món</span>
				{lines.length ? (
					<button type="button" className="pos-cart__clear" onClick={() => clear()}>
						Xoá giỏ
					</button>
				) : null}
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
						const isOpen = expanded === key && groups.length > 0;
						const summary = formatCartOptions(line.options, groups, true);
						const unitExtra = cartUnitSurcharge(line.options, groups);
						const pv = previewFor(idx);
						const promo = hasPromo(pv) ? pv : undefined;
						const metaText = missing.length
							? `Chọn ${missing.map((g) => g.title).join(", ")}`
							: summary || (groups.length ? "Chọn tùy chọn" : "");

						const main = (
							<>
								<span className="pos-cart-line__name">
									<span className="pos-cart-line__name-text">{line.item_name}</span>
									{line.size ? <span className="pos-cart-line__size">{line.size}</span> : null}
								</span>
								{metaText ? (
									<span className="pos-cart-line__meta">
										{metaText ? (
											<span
												className={`pos-cart-line__summary${missing.length ? " is-warn" : ""}`}
											>
												{metaText}
											</span>
										) : null}
										{groups.length ? (
											<span className="pos-cart-line__caret" aria-hidden>
												{isOpen ? "▴" : "▾"}
											</span>
										) : null}
									</span>
								) : null}
								{promo ? (
									<span className="pos-cart-line__promos">
										<PromoChip
											prefix={promo.discount_percentage > 0 ? `Giảm ${promo.discount_percentage}%` : "Khuyến mãi"}
											titles={ruleTitles(promo)}
											full={promoLabel(promo)}
										/>
									</span>
								) : null}
							</>
						);

						return (
							<div
								key={key}
								ref={isOpen ? openRef : undefined}
								className={`pos-cart-line${missing.length ? " is-missing" : ""}${isOpen ? " is-open" : ""}`}
							>
								<div className="pos-cart-line__row">
									{groups.length ? (
										<button
											type="button"
											className="pos-cart-line__main"
											aria-expanded={isOpen}
											title={summary || undefined}
											onClick={() => setExpanded(isOpen ? null : key)}
										>
											{main}
										</button>
									) : (
										<div className="pos-cart-line__main">{main}</div>
									)}

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

									<div className="pos-cart-line__qty">
										<button
											type="button"
											className="pos-step"
											aria-label="Giảm"
											onClick={() => decrement(key)}
										>
											−
										</button>
										<QtyInput value={line.qty} onCommit={(n) => setQty(key, n)} />
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

								{isOpen ? (
									<div className="pos-optgroups">
										<OptionChips
											groups={groups}
											options={line.options}
											onChange={(next) => setExpanded(setLineOptions(key, next))}
										/>
										<div className="pos-optgroups__actions">
											<button
												type="button"
												className="pos-cart-line__delete"
												aria-label="Xoá món"
												onClick={() => removeLine(key)}
											>
												Xoá món
											</button>
										</div>
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
								<div className="pos-cart-line__row">
									<div className="pos-cart-line__main">
										<span className="pos-cart-line__name">
											<span className="pos-cart-line__name-text">{p.item_code}</span>
										</span>
										<span className="pos-cart-line__promos">
											<PromoChip
												prefix="Tặng"
												titles={ruleTitles(p)}
												full={["Tặng", ...ruleTitles(p)].join(" · ")}
											/>
										</span>
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
				{noteOpen ? (
					<textarea
						id="pos-order-note"
						className="pos-input pos-textarea"
						aria-label="Ghi chú đơn hàng"
						placeholder="Ví dụ: ít ngọt, mang đi…"
						value={orderNote}
						onChange={(event) => setOrderNote(event.target.value)}
						onBlur={() => setNoteOpen(false)}
						rows={2}
						autoFocus
					/>
				) : (
					<button
						type="button"
						className="pos-cart__toggle"
						aria-expanded={false}
						onClick={() => setNoteOpen(true)}
					>
						<span className="pos-cart__toggle-label">Ghi chú đơn hàng</span>
						<span className="pos-cart__toggle-value">{orderNote || "Thêm"}</span>
					</button>
				)}

				{canRedeem ? (
					<div className={`pos-redeem${redeemOpen ? " is-open" : ""}`}>
						<button
							type="button"
							className="pos-cart__toggle"
							aria-expanded={redeemOpen}
							onClick={() => setRedeemOpen(!redeemOpen)}
						>
							<span className="pos-cart__toggle-label">Dùng điểm</span>
							<span className="pos-cart__toggle-value">
								{redeemPoints} điểm {redeemOpen ? "▴" : "▾"}
							</span>
						</button>
						{redeemOpen ? (
							<div className="pos-redeem__body">
								<small className="pos-redeem__info">
									Tối đa {maxRedeem} điểm · 1 điểm = {formatMoney(factor, currency)}
								</small>
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
					</div>
				) : null}

				{preview && lines.length ? (
					<div className="pos-cart__sums">
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
						{promoNames ? (
							<div className="pos-cart__promo-names" title={promoNames}>
								{promoNames}
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
					</div>
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

				{children}
			</div>
		</aside>
	);
}
