import { useMemo, useState } from "react";
import { cartUnitSurcharge, defaultOptions, isSelected, missingRequired, plusPrice, toggleOption, valueSurcharge } from "../../lib/options";
import type { CartOption } from "../../types";
import { MAX_LINE_QTY } from "../cart";
import { money } from "../format";
import type { MenuItem } from "../types";
import { IconCheck, IconMinus, IconPlus } from "./icons";
import Sheet from "./Sheet";

/** Chọn size + tùy chọn (MYPOS Option Group động) + số lượng rồi thêm vào giỏ. */
export default function ItemSheet({
	item,
	currency,
	onAdd,
	onClose,
}: {
	item: MenuItem;
	currency: string;
	onAdd: (sizeIndex: number, options: CartOption[], qty: number) => void;
	onClose: () => void;
}) {
	const [sizeIndex, setSizeIndex] = useState(0);
	const [options, setOptions] = useState<CartOption[]>(() => defaultOptions(item.option_groups));
	const [qty, setQty] = useState(1);
	const size = item.sizes[sizeIndex];
	const missing = useMemo(() => missingRequired(options, item.option_groups), [options, item.option_groups]);
	// Giá 1 món theo lựa chọn đang chọn (ước tính để hiển thị; giá thật do server tính khi xem giỏ / đặt đơn).
	const unit = size.rate + cartUnitSurcharge(options, item.option_groups);

	const footer = (
		<div className="qo-addbar">
			<div className="qo-stepper" aria-label="Số lượng">
				<button
					type="button"
					className="qo-stepper__btn"
					aria-label="Bớt 1"
					disabled={qty <= 1}
					onClick={() => setQty((q) => Math.max(1, q - 1))}
				>
					<IconMinus size={18} />
				</button>
				<span key={qty} className="qo-stepper__val" aria-live="polite">
					{qty}
				</span>
				<button
					type="button"
					className="qo-stepper__btn"
					aria-label="Thêm 1"
					disabled={qty >= MAX_LINE_QTY}
					onClick={() => setQty((q) => Math.min(MAX_LINE_QTY, q + 1))}
				>
					<IconPlus size={18} />
				</button>
			</div>
			<button
				type="button"
				className="qo-btn qo-btn--primary qo-btn--lg qo-addbar__cta"
				disabled={missing.length > 0}
				onClick={() => onAdd(sizeIndex, options, qty)}
			>
				{missing.length
					? `Chọn ${missing[0].title}`
					: `Thêm vào giỏ · ${money(unit * qty, currency)}`}
			</button>
		</div>
	);

	return (
		<Sheet title={item.name} onClose={onClose} footer={footer} labelledBy="qo-item-title">
			<div className="qo-item__hero">
				<span className="qo-item__thumb">
					{item.image ? (
						<img src={item.image} alt="" decoding="async" />
					) : (
						<span className="qo-card__initial" aria-hidden="true">
							{item.name.charAt(0)}
						</span>
					)}
				</span>
				<div className="qo-item__info">
					<div className="qo-item__price">{money(unit, currency)}</div>
					{item.sizes.length > 1 ? <div className="qo-item__size">Size {size.label || "Mặc định"}</div> : null}
				</div>
			</div>

			{item.sizes.length > 1 ? (
				<fieldset className="qo-group">
					<legend className="qo-group__title">
						Size <span className="qo-group__req">Bắt buộc</span>
					</legend>
					<div className="qo-chips">
						{item.sizes.map((s, i) => (
							<button
								key={s.item_code}
								type="button"
								aria-pressed={i === sizeIndex}
								className={`qo-chip ${i === sizeIndex ? "is-on" : ""}`}
								onClick={() => setSizeIndex(i)}
							>
								{i === sizeIndex ? <IconCheck size={16} className="qo-chip__check" /> : null}
								<span>{s.label || "Mặc định"}</span>
								<span className="qo-chip__price">{money(s.rate, currency)}</span>
							</button>
						))}
					</div>
				</fieldset>
			) : null}

			{item.option_groups.map((g) => {
				const lacking = missing.some((m) => m.name === g.name);
				return (
					<fieldset key={g.name} className={`qo-group ${lacking ? "is-missing" : ""}`}>
						<legend className="qo-group__title">
							{g.title}{" "}
							<span className="qo-group__req">
								{g.required ? "Bắt buộc" : "Không bắt buộc"}
								{g.selection_type === "Chọn nhiều" ? " · chọn nhiều" : ""}
							</span>
						</legend>
						<div className="qo-chips">
							{g.values.map((v) => {
								const on = isSelected(options, g.name, v.label);
								return (
									<button
										key={v.label}
										type="button"
										aria-pressed={on}
										className={`qo-chip ${on ? "is-on" : ""}`}
										onClick={() => setOptions((o) => toggleOption(o, g, v.label))}
									>
										{on ? <IconCheck size={16} className="qo-chip__check" /> : null}
										<span>{v.label}</span>
										{valueSurcharge(item.option_groups, g.name, v.label) > 0 ? (
											<span className="qo-chip__price">
												{plusPrice(valueSurcharge(item.option_groups, g.name, v.label))}
											</span>
										) : null}
									</button>
								);
							})}
						</div>
					</fieldset>
				);
			})}
		</Sheet>
	);
}
