import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import MenuGrid from "../components/MenuGrid";
import CartPanel from "../components/CartPanel";
import CustomerPicker from "../components/CustomerPicker";
import BuzzerPicker from "../components/BuzzerPicker";
import { api } from "../lib/api";
import { missingRequired } from "../lib/options";
import { usePos } from "../lib/pos-context";
import { useCart, cartCount } from "../store/cart";
import { useSearch } from "../store/search";
import type { BuzzerOption, CustomerOption, LoyaltyInfo, OrderType, PricingPreview } from "../types";

export default function POS() {
	const navigate = useNavigate();
	const { config, loading, error, menus } = usePos();
	const lines = useCart((state) => state.lines);
	const clear = useCart((state) => state.clear);
	const orderNote = useCart((state) => state.orderNote);
	const search = useSearch((state) => state.search);
	const redeemPoints = useCart((state) => state.redeemPoints);
	const setRedeemPoints = useCart((state) => state.setRedeemPoints);

	const [orderType, setOrderType] = useState<OrderType>("Take Away");
	const [customer, setCustomer] = useState<CustomerOption | null>(null);
	const [buzzer, setBuzzer] = useState<BuzzerOption | null>(null);
	const [pickerOpen, setPickerOpen] = useState(false);
	const [modeOfPayment] = useState("");
	const [submitting, setSubmitting] = useState(false);
	const [formError, setFormError] = useState("");
	const [loyalty, setLoyalty] = useState<LoyaltyInfo | null>(null);
	const [preview, setPreview] = useState<PricingPreview | null>(null);
	const [previewError, setPreviewError] = useState("");
	const [previewLoading, setPreviewLoading] = useState(false);

	// Price List lấy từ menu đầu tiên có price_list.
	const priceList = useMemo(
		() => menus?.find((m) => m.price_list)?.price_list || null,
		[menus]
	);

	// Đổi khách -> bỏ điểm đang chọn.
	useEffect(() => {
		setRedeemPoints(0);
	}, [customer?.name, setRedeemPoints]);

	// Hạng + điểm của khách (chip). Mức đổi tối đa lấy từ preview (tính sau CTKM).
	useEffect(() => {
		const name = customer?.name;
		if (!name) {
			setLoyalty(null);
			return;
		}
		let cancelled = false;
		api
			.getCustomerLoyalty(name)
			.then((info) => {
				if (!cancelled) setLoyalty(info?.enrolled ? info : null);
			})
			.catch(() => {
				if (!cancelled) setLoyalty(null);
			});
		return () => {
			cancelled = true;
		};
	}, [customer?.name]);

	// Dòng gửi server: mã + số lượng + tùy chọn, đúng thứ tự dòng giỏ (preview ghép theo vị trí).
	// Tùy chọn không đổi giá nhưng server kiểm tra hợp lệ, nên vẫn nằm trong khóa preview.
	const orderItems = useMemo(
		() => lines.map((l) => ({ item_code: l.item_code, qty: l.qty, options: l.options })),
		[lines]
	);
	const pricingKey = lines.length ? JSON.stringify(orderItems) : "";
	const missingLine = lines.find((l) => missingRequired(l.options, l.option_groups).length);

	// Xem trước giá sau CTKM + đổi điểm (trễ 300ms, bỏ kết quả cũ).
	useEffect(() => {
		if (!pricingKey || !priceList) {
			setPreview(null);
			setPreviewError("");
			setPreviewLoading(false);
			return;
		}
		const items = JSON.parse(pricingKey) as typeof orderItems;
		const base = { items, customer: customer?.name, price_list: priceList };
		let cancelled = false;
		setPreviewLoading(true);
		const timer = window.setTimeout(async () => {
			try {
				const res = await api.previewPricing({ ...base, redeem_points: redeemPoints || undefined });
				if (cancelled) return;
				setPreview(res);
				setPreviewError("");
			} catch (err) {
				if (cancelled) return;
				// Điểm đang chọn vượt mức mới (giỏ vừa giảm) -> lấy mức tối đa rồi ép điểm.
				if (redeemPoints > 0) {
					try {
						const res0 = await api.previewPricing(base);
						if (cancelled) return;
						const max0 = res0.max_redeem_points || 0;
						if (max0 < redeemPoints) {
							// Effect chạy lại với số điểm mới.
							setRedeemPoints(max0);
							return;
						}
					} catch {
						/* rơi xuống báo lỗi */
					}
				}
				if (!cancelled) {
					setPreview(null);
					setPreviewError(err instanceof Error ? err.message : String(err));
				}
			} finally {
				if (!cancelled) setPreviewLoading(false);
			}
		}, 300);
		return () => {
			cancelled = true;
			window.clearTimeout(timer);
		};
	}, [pricingKey, customer?.name, redeemPoints, priceList, setRedeemPoints]);

	const usableModes = useMemo(
		() => (config?.payment_modes || []).filter((mode) => mode.has_account),
		[config]
	);

	const selectedMode = modeOfPayment || usableModes[0]?.name || "";
	const needBuzzer = orderType === "Dine In" && !buzzer;
	const canSubmit =
		!submitting && !loading && lines.length > 0 && !!priceList && !needBuzzer && !missingLine;

	const chooseDineIn = () => {
		setOrderType("Dine In");
		setPickerOpen(true);
	};

	const chooseTakeAway = () => {
		setOrderType("Take Away");
		setBuzzer(null);
	};

	const createOrder = async () => {
		if (!lines.length) {
			setFormError("Chưa chọn món nào để tạo đơn.");
			return;
		}
		if (!priceList) {
			setFormError("Thiếu Price List của menu.");
			return;
		}
		if (needBuzzer) {
			setFormError("Chọn thẻ rung cho đơn tại quán.");
			return;
		}
		if (missingLine) {
			setFormError(`Chọn đủ tùy chọn bắt buộc cho món ${missingLine.item_name}.`);
			return;
		}

		setSubmitting(true);
		setFormError("");
		try {
			const result = await api.createDraftOrder({
				items: orderItems,
				order_type: orderType,
				customer_name: customer?.name,
				mode_of_payment: selectedMode || undefined,
				price_list: priceList,
				order_note: orderNote.trim() || undefined,
				buzzer: orderType === "Dine In" ? buzzer?.name : undefined,
				redeem_points: redeemPoints > 0 ? redeemPoints : undefined,
			});

			clear();
			setCustomer(null);
			setBuzzer(null);
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
							onClick={chooseDineIn}
						>
							Tại quán
						</button>
						<button
							type="button"
							className={orderType === "Take Away" ? "is-active" : ""}
							onClick={chooseTakeAway}
						>
							Mang đi
						</button>
					</div>

					{orderType === "Dine In" ? (
						<button
							type="button"
							className="pos-buzzer-chosen"
							onClick={() => setPickerOpen(true)}
						>
							{buzzer ? `Thẻ rung #${buzzer.buzzer_number} · Đổi thẻ` : "Chọn thẻ rung"}
						</button>
					) : null}

					<CustomerPicker value={customer} onChange={setCustomer} />
					{loyalty ? (
						<div className="pos-loyalty-chip">
							{loyalty.tier_name ? `Hạng ${loyalty.tier_name} · ` : ""}
							{loyalty.loyalty_points ?? 0} điểm
						</div>
					) : null}
				</section>

				<CartPanel
					loyalty={loyalty}
					preview={preview}
					previewError={previewError}
					previewLoading={previewLoading}
				>
					{/* Cảnh báo + Tạo đơn nằm trong chân giỏ: luôn hiện, không cuộn theo danh sách món. */}
					{formError ? <div className="pos-alert pos-alert--error">{formError}</div> : null}
					{missingLine ? (
						<div className="pos-cart__hint pos-cart__hint--error">
							Món {missingLine.item_name} còn tùy chọn bắt buộc chưa chọn.
						</div>
					) : null}
					{needBuzzer && lines.length > 0 ? (
						<div className="pos-alert pos-alert--error">Chọn thẻ rung cho đơn tại quán.</div>
					) : null}
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
				</CartPanel>
			</aside>

			<BuzzerPicker
				open={pickerOpen}
				selected={buzzer?.name || null}
				onClose={() => setPickerOpen(false)}
				onPick={(b) => {
					setBuzzer(b);
					setPickerOpen(false);
				}}
			/>
		</div>
	);
}