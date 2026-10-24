import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import MenuGrid from "../components/MenuGrid";
import CartPanel from "../components/CartPanel";
import CustomerPicker from "../components/CustomerPicker";
import { api } from "../lib/api";
import { usePos } from "../lib/pos-context";
import { useCart, cartCount } from "../store/cart";
import { useSearch } from "../store/search";
import type { CustomerOption, OrderType } from "../types";

export default function POS() {
	const navigate = useNavigate();
	const { config, loading, error, menus } = usePos();
	const lines = useCart((state) => state.lines);
	const clear = useCart((state) => state.clear);
	const search = useSearch((state) => state.search);

	const [orderType, setOrderType] = useState<OrderType>("Take Away");
	const [customer, setCustomer] = useState<CustomerOption | null>(null);
	const [modeOfPayment, setModeOfPayment] = useState("");
	const [submitting, setSubmitting] = useState(false);
	const [formError, setFormError] = useState("");
	const orderNote = useCart((state) => state.orderNote);

	// Price List lấy từ menu đầu tiên có price_list.
	const priceList = useMemo(
		() => menus?.find((m) => m.price_list)?.price_list || null,
		[menus]
	);

	const usableModes = useMemo(
		() => (config?.payment_modes || []).filter((mode) => mode.has_account),
		[config]
	);

	const selectedMode = modeOfPayment || usableModes[0]?.name || "";
	const canSubmit = !submitting && !loading && lines.length > 0 && !!priceList;

	const createOrder = async () => {
		if (!lines.length) {
			setFormError("Chưa chọn món nào để tạo đơn.");
			return;
		}
		if (!priceList) {
			setFormError("Thiếu Price List của menu.");
			return;
		}

		setSubmitting(true);
		setFormError("");
		try {
			const result = await api.createDraftOrder({
				items: lines.map((line) => ({
				item_code: line.item_code,
				qty: line.qty,
				sugar: line.sugar ?? 100,
				ice: line.ice ?? 100,
				})),
				order_type: orderType,
				customer_name: customer?.name,
				mode_of_payment: selectedMode || undefined,
				price_list: priceList,
				order_note: orderNote.trim() || undefined,
			});

			clear();
			setCustomer(null);
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
				{error ? <div className="pos-alert pos-alert--error">{error}</div> : null}
				{loading ? (
					<div className="pos-empty">Đang tải menu…</div>
				) : (
					<MenuGrid search={search} />
				)}
			</div>

			<aside className="pos-page__side">
				<section className="pos-order-setup">
					<div className="pos-segmented pos-segmented--full" role="tablist">
						<button
							type="button"
							className={orderType === "Dine In" ? "is-active" : ""}
							onClick={() => setOrderType("Dine In")}
						>
							Tại quán
						</button>
						<button
							type="button"
							className={orderType === "Take Away" ? "is-active" : ""}
							onClick={() => setOrderType("Take Away")}
						>
							Mang đi
						</button>
					</div>

					<CustomerPicker value={customer} onChange={setCustomer} />

					{/* <select
						id="pos-mop"
						className="pos-input"
						aria-label="Phương thức thanh toán"
						value={selectedMode}
						onChange={(event) => setModeOfPayment(event.target.value)}
					>
						{!usableModes.length ? (
							<option value="">Chưa có phương thức thanh toán</option>
						) : null}
						{usableModes.map((mode) => (
							<option key={mode.name} value={mode.name}>
								{mode.label || mode.name}
							</option>
						))}
					</select> */}
				</section>

				<CartPanel />

				{formError ? <div className="pos-alert pos-alert--error">{formError}</div> : null}
				{!loading && !priceList ? (
					<div className="pos-alert pos-alert--error">
						Thiếu Price List của menu — không thể tạo đơn.
					</div>
				) : null}

				<div className="pos-create-bar">
					<span className="pos-create-bar__count">{cartCount(lines)} món</span>
					<button
						type="button"
						className="pos-btn pos-btn--primary pos-btn--block"
						disabled={!canSubmit}
						onClick={createOrder}
					>
						{submitting ? "Đang tạo…" : "Tạo đơn"}
					</button>
				</div>
			</aside>
		</div>
	);
}