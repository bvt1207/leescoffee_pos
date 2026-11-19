import { useState } from "react";
import { formatMoney } from "../store/cart";
import { usePos } from "../lib/pos-context";
import { cartUnitSurcharge, defaultOptions, missingRequired } from "../lib/options";
import type { CartOption, MenuItem, MenuSize } from "../types";
import ItemModalFrame from "./ItemModalFrame";
import OptionChips from "./OptionChips";

interface Props {
	item: MenuItem;
	size: MenuSize;
	onClose: () => void;
	onAdd: (options: CartOption[]) => void;
}

/**
 * Món 1 size có tùy chọn: chọn tùy chọn trước khi thêm. Giá ở chân bảng (cột phải, cùng chỗ với giá
 * hàng size) = giá món + phụ thu ước tính từ menu; giá thật (CTKM, phụ thu) do preview ở giỏ tính.
 * Component cha chỉ render khi mở, nên lựa chọn khởi tạo lại mặc định mỗi lần mở.
 */
export default function OptionModal({ item, size, onClose, onAdd }: Props) {
	const { config } = usePos();
	const currency = config?.profile?.currency || "VND";
	const groups = item.option_groups || [];
	const [options, setOptions] = useState<CartOption[]>(() => defaultOptions(groups));
	const missing = missingRequired(options, groups);
	const price = (size.rate ?? 0) + cartUnitSurcharge(options, groups);

	return (
		<ItemModalFrame
			item={item}
			hint="Chọn tùy chọn"
			onClose={onClose}
			footer={
				<>
					<div className="pos-item-modal__price-row">
						<span className={`pos-item-modal__hint${missing.length ? " is-warn" : ""}`}>
							{missing.length ? `Chọn ${missing.map((g) => g.title).join(", ")}` : "Giá"}
						</span>
						<span className="pos-item-modal__price">{formatMoney(price, currency)}</span>
					</div>
					<button
						type="button"
						className="pos-btn pos-btn--primary pos-btn--block"
						disabled={missing.length > 0}
						onClick={() => onAdd(options)}
					>
						Thêm vào giỏ
					</button>
				</>
			}
		>
			<div className="pos-optgroups pos-optgroups--modal">
				<OptionChips groups={groups} options={options} onChange={setOptions} />
			</div>
		</ItemModalFrame>
	);
}
