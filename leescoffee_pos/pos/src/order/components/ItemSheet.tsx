import { useMemo, useState } from "react";
import { defaultOptions, isSelected, missingRequired, toggleOption } from "../../lib/options";
import type { CartOption } from "../../types";
import { MAX_LINE_QTY } from "../cart";
import { money } from "../format";
import type { MenuItem } from "../types";
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
					−
				</button>
				<span className="qo-stepper__val" aria-live="polite">
					{qty}
				</span>
				<button
					type="button"
					className="qo-stepper__btn"
					aria-label="Thêm 1"
					disabled={qty >= MAX_LINE_QTY}
					onClick={() => setQty((q) => Math.min(MAX_LINE_QTY, q + 1))}
				>
					+
				</button>
			</div>
			<button
				type="button"
				className="qo-btn qo-btn--primary qo-addbar__cta"
				disabled={missing.length > 0}
				onClick={() => onAdd(sizeIndex, options, qty)}
			>
				{missing.length ? `Chọn ${missing[0].title}` : `Thêm · ${money(size.rate * qty, currency)}`}
			</button>
		</div>
	);

	return (
		<Sheet title={item.name} onClose={onClose} footer={footer} labelledBy="qo-item-title">
			{item.image ? <img className="qo-item__img" src={item.image} alt="" /> : null}

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
										{v.label}
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
