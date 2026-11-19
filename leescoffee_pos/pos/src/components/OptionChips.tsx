import { isSelected, missingRequired, plusPrice, toggleOption, valueSurcharge } from "../lib/options";
import type { CartOption, OptionGroup } from "../types";

interface Props {
	groups: OptionGroup[];
	options: CartOption[];
	/** Trả về tổ hợp tùy chọn mới sau khi bấm một chip. */
	onChange: (options: CartOption[]) => void;
}

/**
 * Chip tùy chọn món (MYPOS Option Group): nhãn nhóm cùng hàng với chip, mặt chip 30px trong vùng chạm 44px,
 * "+giá" cho giá trị có phụ thu, nhắc nhóm bắt buộc chưa chọn. Dùng chung cho giỏ (CartPanel) và OptionModal.
 */
export default function OptionChips({ groups, options, onChange }: Props) {
	const missing = missingRequired(options, groups);
	return (
		<>
			{groups.map((g) => {
				const groupMissing = missing.some((m) => m.name === g.name);
				return (
					<div key={g.name} className={`pos-optgroup${groupMissing ? " is-missing" : ""}`}>
						<span className="pos-optgroup__title">
							{g.title}
							{g.required ? <span className="pos-optgroup__req"> *</span> : null}
							{g.selection_type === "Chọn nhiều" ? (
								<span className="pos-optgroup__hint">chọn nhiều</span>
							) : null}
							{groupMissing ? (
								<span className="pos-optgroup__hint pos-optgroup__hint--warn">chưa chọn</span>
							) : null}
						</span>
						<div
							className="pos-optchips"
							role={g.selection_type === "Chọn 1" ? "radiogroup" : "group"}
							aria-label={g.title}
						>
							{g.values.map((v) => {
								const on = isSelected(options, g.name, v.label);
								const extra = valueSurcharge(groups, g.name, v.label);
								return (
									<button
										type="button"
										key={v.label}
										className={`pos-optchip${on ? " is-active" : ""}`}
										role={g.selection_type === "Chọn 1" ? "radio" : "checkbox"}
										aria-checked={on}
										onClick={() => onChange(toggleOption(options, g, v.label))}
									>
										<span className="pos-optchip__face">
											{v.label}
											{extra > 0 ? <span className="pos-optchip__price">{plusPrice(extra)}</span> : null}
										</span>
									</button>
								);
							})}
						</div>
					</div>
				);
			})}
		</>
	);
}
