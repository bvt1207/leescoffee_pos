import { useCart, cartTotal, cartCount, formatMoney } from "../store/cart";
import { usePos } from "../lib/pos-context";

export default function CartPanel() {
	const lines = useCart((state) => state.lines);
	const increment = useCart((state) => state.increment);
	const decrement = useCart((state) => state.decrement);
	const remove = useCart((state) => state.remove);
	const clear = useCart((state) => state.clear);
	const { config } = usePos();

	const currency = config?.profile?.currency || "VND";
	const total = cartTotal(lines);
	const count = cartCount(lines);

	return (
		<aside className="pos-cart">
			<div className="pos-cart__header">
				<h2>Giỏ hàng</h2>
				<span className="pos-badge">{count} món</span>
			</div>

			<div className="pos-cart__lines">
				{!lines.length ? (
					<div className="pos-empty">Chưa chọn món nào.</div>
				) : (
					lines.map((line) => (
						<div key={line.item_code} className="pos-cart-line">
							<div className="pos-cart-line__info">
								<div className="pos-cart-line__name">{line.item_name}</div>
								<div className="pos-cart-line__price">{formatMoney(line.price, currency)}</div>
							</div>
							<div className="pos-cart-line__qty">
								<button
									type="button"
									className="pos-step"
									onClick={() => decrement(line.item_code)}
								>
									−
								</button>
								<span className="pos-cart-line__qty-value">{line.qty}</span>
								<button
									type="button"
									className="pos-step"
									onClick={() => increment(line.item_code)}
								>
									+
								</button>
							</div>
							<button
								type="button"
								className="pos-cart-line__remove"
								title="Xoá món"
								onClick={() => remove(line.item_code)}
							>
								×
							</button>
						</div>
					))
				)}
			</div>

			<div className="pos-cart__footer">
				<div className="pos-cart__total">
					<span>Tổng cộng</span>
					<strong>{formatMoney(total, currency)}</strong>
				</div>
				{lines.length ? (
					<button type="button" className="pos-btn pos-btn--ghost" onClick={clear}>
						Xoá giỏ
					</button>
				) : null}
			</div>
		</aside>
	);
}
