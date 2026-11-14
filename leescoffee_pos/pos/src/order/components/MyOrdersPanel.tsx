import { formatOptions } from "../../lib/options";
import { clock, hhmm, money, orderTypeLabel } from "../format";
import type { CustomerOrder } from "../types";
import Sheet from "./Sheet";

const STEPS: Array<{ stage: CustomerOrder["stage"]; label: string }> = [
	{ stage: "queued", label: "Chưa làm" },
	{ stage: "ready", label: "Đã làm" },
	{ stage: "done", label: "Đã hoàn thành" },
];

/** "Đơn của tôi": đơn của phiên này (server lọc theo phiên), làm mới 5 giây ở OrderApp. */
export default function MyOrdersPanel({
	orders,
	onPay,
	onClose,
}: {
	orders: CustomerOrder[];
	onPay: (invoiceName: string) => void;
	onClose: () => void;
}) {
	return (
		<Sheet title="Đơn của tôi" onClose={onClose} labelledBy="qo-orders-title">
			{!orders.length ? (
				<div className="qo-empty">Bạn chưa có đơn nào trong phiên này.</div>
			) : (
				<ul className="qo-orders">
					{orders.map((o) => {
						const stepIndex = STEPS.findIndex((s) => s.stage === o.stage);
						return (
							<li key={o.invoice_name} className={`qo-order qo-order--${o.stage}`}>
								<div className="qo-order__head">
									<div>
										<div className="qo-order__id">{o.invoice_name}</div>
										<div className="qo-order__meta">
											{orderTypeLabel(o.order_type)} · {hhmm(o.creation)} · {money(o.amount, o.currency)}
										</div>
									</div>
									<span className={`qo-badge qo-badge--${o.stage}`}>{o.stage_label}</span>
								</div>

								{stepIndex >= 0 ? (
									<ol className="qo-steps" aria-label="Tiến độ pha chế">
										{STEPS.map((s, i) => (
											<li
												key={s.stage}
												className={`qo-steps__item ${i <= stepIndex ? "is-done" : ""}`}
												aria-current={i === stepIndex ? "step" : undefined}
											>
												{s.label}
											</li>
										))}
									</ol>
								) : null}

								{o.stage === "ready" ? (
									<div className="qo-order__ready">Món đã sẵn sàng, mời {o.customer_name} đến quầy nhận.</div>
								) : null}

								<ul className="qo-order__items">
									{o.items.map((it, i) => {
										const opts = formatOptions(it.options);
										return (
											<li key={i}>
												{it.qty}× {it.item_name}
												{it.size ? ` · ${it.size}` : ""}
												{opts ? <span className="qo-order__opts"> — {opts}</span> : null}
											</li>
										);
									})}
								</ul>

								{o.stage === "awaiting_payment" ? (
									<div className="qo-order__pay">
										<span>Còn {clock(o.expires_in ?? 0)} để thanh toán</span>
										<button
											type="button"
											className="qo-btn qo-btn--primary qo-btn--sm"
											onClick={() => onPay(o.invoice_name)}
										>
											Thanh toán
										</button>
									</div>
								) : null}
								{o.stage === "expired" ? (
									<div className="qo-fine">
										Đơn hết hạn thanh toán. Nếu đã chuyển khoản, vui lòng báo nhân viên kèm mã đơn.
									</div>
								) : null}
							</li>
						);
					})}
				</ul>
			)}
		</Sheet>
	);
}
