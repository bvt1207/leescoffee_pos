import { usePos } from "../lib/pos-context";
import { useCart } from "../store/cart";
import { formatMoney } from "../store/cart";
import type { MenuItem } from "../types";

function MenuCard({ item, currency }: { item: MenuItem; currency: string }) {
	const add = useCart((state) => state.add);
	const qty = useCart((state) =>
		state.lines.find((line) => line.item_code === item.item_code)?.qty || 0
	);

	return (
		<div className="pos-menu-card">
			<div className="pos-menu-card__top">
				<div className="pos-menu-card__name">{item.item_name}</div>
				{qty > 0 ? <span className="pos-badge">x{qty}</span> : null}
			</div>
			<div className="pos-menu-card__price">
				{item.price ? formatMoney(item.price, currency) : "Chưa có giá"}
			</div>
			<div className="pos-menu-card__actions">
				<button
					type="button"
					className="pos-btn pos-btn--ghost"
					disabled={!item.price}
					onClick={() =>
						add({
							item_code: item.item_code,
							item_name: item.item_name,
							item_type: item.item_type,
							price: item.price,
							qty: 1,
						})
					}
				>
					+ Thêm
				</button>
			</div>
		</div>
	);
}

export default function MenuGrid() {
	const { menus, config } = usePos();
	const currency = config?.profile?.currency || "VND";

	if (!menus.length) {
		return <div className="pos-empty">Chưa có menu nào được cấu hình.</div>;
	}

	return (
		<div className="pos-menu-groups">
			{menus.map((group) => (
				<section key={group.name} className="pos-menu-group">
					<h2 className="pos-menu-group__title">{group.menu_name || group.name}</h2>
					<div className="pos-menu-grid">
						{(group.items || []).map((item) => (
							<MenuCard key={`${group.name}-${item.idx}-${item.item_code}`} item={item} currency={currency} />
						))}
					</div>
				</section>
			))}
		</div>
	);
}
