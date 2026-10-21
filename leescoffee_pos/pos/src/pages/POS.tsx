import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import MenuGrid from "../components/MenuGrid";
import CartPanel from "../components/CartPanel";
import { api } from "../lib/api";
import { usePos } from "../lib/pos-context";
import { useCart, cartCount } from "../store/cart";
import type { OrderType } from "../types";

export default function POS() {
	const navigate = useNavigate();
	const { config, loading, error } = usePos();
	const lines = useCart((state) => state.lines);
	const clear = useCart((state) => state.clear);

	const [orderType, setOrderType] = useState<OrderType>("Take Away");
	const [customerName, setCustomerName] = useState("");
	const [modeOfPayment, setModeOfPayment] = useState("");
	const [submitting, setSubmitting] = useState(false);
	const [formError, setFormError] = useState("");

	const usableModes = useMemo(
		() => (config?.payment_modes || []).filter((mode) => mode.has_account),
		[config]
	);

	const selectedMode = modeOfPayment || usableModes[0]?.name || "";

	const createOrder = async () => {
		if (!lines.length) {
			setFormError("Chưa chọn món nào để tạo đơn.");
			return;
		}

		setSubmitting(true);
		setFormError("");
		try {
			const result = await api.createDraftOrder({
				items: lines.map((line) => ({
					item_code: line.item_code,
					qty: line.qty,
				})),
				order_type: orderType,
				customer_name: customerName.trim() || undefined,
				mode_of_payment: selectedMode || undefined,
			});

			clear();
			navigate(`/orders?draft=${encodeURIComponent(result.invoice_name)}`);
		} catch (err) {
			setFormError(err instanceof Error ? err.message : String(err));
		} finally {
			setSubmitting(false);
		}
	};

	return (
		<div className="pos-page pos-page--split">
			<div className="pos-page__main">
				<section className="pos-toolbar">
					<div className="pos-toolbar__group">
						<span className="pos-toolbar__label">Loại đơn</span>
						<div className="pos-segmented">
							<button
								type="button"
								className={orderType === "Take Away" ? "is-active" : ""}
								onClick={() => setOrderType("Take Away")}
							>
								Mang đi
							</button>
							<button
								type="button"
								className={orderType === "Dine In" ? "is-active" : ""}
								onClick={() => setOrderType("Dine In")}
							>
								Tại quầy
							</button>
						</div>
					</div>

					<div className="pos-toolbar__group">
						<label className="pos-toolbar__label" htmlFor="pos-customer">
							Tên khách
						</label>
						<input
							id="pos-customer"
							className="pos-input"
							placeholder="Không bắt buộc"
							value={customerName}
							onChange={(event) => setCustomerName(event.target.value)}
						/>
					</div>

					<div className="pos-toolbar__group">
						<label className="pos-toolbar__label" htmlFor="pos-mop">
							Thanh toán
						</label>
						<select
							id="pos-mop"
							className="pos-input"
							value={selectedMode}
							onChange={(event) => setModeOfPayment(event.target.value)}
						>
							{!usableModes.length ? <option value="">Chưa có phương thức thanh toán</option> : null}
							{usableModes.map((mode) => (
								<option key={mode.name} value={mode.name}>
									{mode.label || mode.name}
								</option>
							))}
						</select>
					</div>
				</section>

				{error ? <div className="pos-alert pos-alert--error">{error}</div> : null}
				{formError ? <div className="pos-alert pos-alert--error">{formError}</div> : null}

				{loading ? <div className="pos-empty">Đang tải menu…</div> : <MenuGrid />}
			</div>

			<div className="pos-page__side">
				<CartPanel />
				<div className="pos-create-bar">
					<span className="pos-create-bar__count">{cartCount(lines)} món</span>
					<button
						type="button"
						className="pos-btn pos-btn--primary pos-btn--block"
						disabled={submitting || loading || !lines.length}
						onClick={createOrder}
					>
						{submitting ? "Đang tạo…" : "Tạo đơn"}
					</button>
				</div>
			</div>
		</div>
	);
}
