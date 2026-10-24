import { useCart, cartLineKey, cartTotal, cartCount, formatMoney } from "../store/cart";
import { usePos } from "../lib/pos-context";

const LEVELS = [50, 70, 100] as const;

export default function CartPanel() {
	const lines = useCart((state) => state.lines);
	const increment = useCart((state) => state.increment);
	const decrement = useCart((state) => state.decrement);
	const removeLine = useCart((state) => state.removeLine);
	const changeIceSugar = useCart((state) => state.changeIceSugar);
	const orderNote = useCart((state) => state.orderNote);
	const setOrderNote = useCart((state) => state.setOrderNote);
	const clear = useCart((state) => state.clear);
	const { config } = usePos();

	const currency = config?.profile?.currency || "VND";
	const total = cartTotal(lines);
	const count = cartCount(lines);

	// TODO: đường/đá/ghi chú chưa gửi server — chỉ giữ trong state.
	// Backend sẽ thêm custom field ở task sau.

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
					lines.map((line) => {
						const key = cartLineKey(line);
						const sugar = line.sugar ?? 100;
						const ice = line.ice ?? 100;
						return (
							<div key={key} className="pos-cart-line">
								<div className="pos-cart-line__head">
									<div className="pos-cart-line__name">
										{line.item_name}
										{line.size ? (
											<span className="pos-cart-line__size">{line.size}</span>
										) : null}
									</div>
									<div className="pos-cart-line__price">
										{formatMoney(line.price * line.qty, currency)}
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

								<div className="pos-cart-line__body">
									<div className="pos-cart-line__options">
										<div className="pos-cart-line__option">
											<span className="pos-cart-line__option-label">Đường</span>
											<div className="pos-segmented pos-segmented--sm">
												{LEVELS.map((v) => (
													<button
														type="button"
														key={`sugar-${v}`}
														className={sugar === v ? "is-active" : ""}
														onClick={() => changeIceSugar(key, ice, v)}
													>
														{v}%
													</button>
												))}
											</div>
										</div>
										<div className="pos-cart-line__option">
											<span className="pos-cart-line__option-label">Đá</span>
											<div className="pos-segmented pos-segmented--sm">
												{LEVELS.map((v) => (
													<button
														type="button"
														key={`ice-${v}`}
														className={ice === v ? "is-active" : ""}
														onClick={() => changeIceSugar(key, v, sugar)}
													>
														{v}%
													</button>
												))}
											</div>
										</div>
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

								{line.note ? <div className="pos-cart-line__note">{line.note}</div> : null}
							</div>
						);
					})
				)}
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
				<div className="pos-cart__total">
					<span>Tổng cộng</span>
					<strong>{formatMoney(total, currency)}</strong>
				</div>
				{lines.length ? (
					<button type="button" className="pos-btn pos-btn--ghost" onClick={() => clear()}>
						Xoá giỏ
					</button>
				) : null}
			</div>
		</aside>
	);
}