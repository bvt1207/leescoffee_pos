import { createPortal } from "react-dom";
import type { KitchenOrder, OrderDetail } from "../types";

/** Một ly = một tem. i chạy 1..n trên toàn đơn. */
export interface Cup {
	key: string;
	itemIndex: number;
	name: string;
	size: string;
	sugar: string;
	ice: string;
	i: number;
	n: number;
}

export interface LabelJob {
	order: KitchenOrder;
	cups: Cup[];
}

const cupCount = (qty: number) => Math.max(1, Math.round(qty || 0));

/** Số thứ tự ly (1..n) của từng món, chỉ dựa trên qty — dùng để vẽ nút trên thẻ. */
export function cupIndexes(order: KitchenOrder): { per: number[][]; n: number } {
	let next = 1;
	const per = order.items.map((it) => {
		const list: number[] = [];
		for (let k = 0; k < cupCount(it.qty); k += 1) list.push(next++);
		return list;
	});
	return { per, n: next - 1 };
}

/** Trải phẳng món thành danh sách ly; size lấy từ getOrderDetail (ghép theo vị trí món). */
export function buildCups(order: KitchenOrder, detail: OrderDetail | null): Cup[] {
	const { per, n } = cupIndexes(order);
	const cups: Cup[] = [];
	order.items.forEach((it, idx) => {
		const d = detail?.items[idx];
		const size = d && d.item_code === it.item_code ? d.size || "" : "";
		per[idx].forEach((i) => {
			cups.push({
				key: `${order.name}-${i}`,
				itemIndex: idx,
				name: it.item_name,
				size,
				sugar: it.sugar_level || "100",
				ice: it.ice_level || "100",
				i,
				n,
			});
		});
	});
	return cups;
}

/** Phần tử chỉ hiện khi in (portal ngoài #root). Mỗi tem là một trang. */
export default function CupLabels({ job }: { job: LabelJob | null }) {
	if (!job) return null;
	const { order, cups } = job;
	const who = order.buzzer_number ? `Thẻ #${order.buzzer_number}` : order.customer_name;

	return createPortal(
		<div className="pos-print-only">
			{cups.map((c) => (
				<div key={c.key} className="pos-label">
					<div className="pos-label__name">
						{c.name}
						{c.size ? ` (${c.size})` : ""}
					</div>
					<div className="pos-label__opts">
						Đường {c.sugar}% · Đá {c.ice}%
					</div>
					{order.order_note ? <div className="pos-label__note">{order.order_note}</div> : null}
					<div className="pos-label__foot">
						<span>{order.name}</span>
						<span>
							{c.i}/{c.n}
						</span>
					</div>
					<div className="pos-label__who">{who}</div>
				</div>
			))}
		</div>,
		document.body
	);
}
