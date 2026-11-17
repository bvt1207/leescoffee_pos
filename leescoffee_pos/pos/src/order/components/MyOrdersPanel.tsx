import { formatOptions } from "../../lib/options";
import { clock, hhmm, money, orderTypeLabel } from "../format";
import type { CustomerOrder } from "../types";
import Sheet from "./Sheet";

const STEPS: Array<{ stage: CustomerOrder["stage"]; label: string }> = [
	{ stage: "queued", label: "Chưa làm" },
	{ stage: "ready", label: "Đã làm" },
	{ stage: "done", label: "Đã hoàn thành" },
];

/** Nhóm do server chia; thiếu `group` (server cũ) thì đơn còn xử lý = active. */
const isActive = (o: CustomerOrder) =>
	o.group ? o.group === "active" : o.stage === "awaiting_payment" || o.stage === "queued" || o.stage === "ready";

/**
 * "Đơn của tôi": đơn của KHÁCH tại chi nhánh này (server lọc theo khách + chi nhánh, không theo phiên),
 * chia "Đang xử lý" và "Lịch sử" (30 ngày, tối đa 30 đơn). OrderApp poll 5 giây khi còn đơn đang xử lý.
 */
export default function MyOrdersPanel({
	orders,
	onPay,
	onClose,
}: {
	orders: CustomerOrder[];
	onPay: (invoiceName: string) => void;
	onClose: () => void;
}) {
	const active = orders.filter(isActive);
	const history = orders.filter((o) => !isActive(o));

	return (
		<Sheet title="Đơn của tôi" onClose={onClose} labelledBy="qo-orders-title">
			<section className="qo-orders-group" aria-labelledby="qo-orders-active">
				<h3 id="qo-orders-active" className="qo-cart__label qo-orders-group__title">
					Đang xử lý
				</h3>
				{active.length ? (
					<ul className="qo-orders">
						{active.map((o) => (
							<OrderCard key={o.invoice_name} order={o} onPay={onPay} />
						))}
					</ul>
				) : (
					<div className="qo-empty qo-empty--sm">Không có đơn nào đang chờ. Chọn món để đặt đơn mới nhé.</div>
				)}
			</section>

			<section className="qo-orders-group" aria-labelledby="qo-orders-history">
				<h3 id="qo-orders-history" className="qo-cart__label qo-orders-group__title">
					Lịch sử (30 ngày)
				</h3>
				{history.length ? (
					<ul className="qo-orders">
						{history.map((o) => (
							<OrderCard key={o.invoice_name} order={o} onPay={onPay} />
						))}
					</ul>
				) : (
					<div className="qo-empty qo-empty--sm">Chưa có đơn đã thanh toán tại quán này.</div>
				)}
			</section>
		</Sheet>
	);
}

function OrderCard({ order: o, onPay }: { order: CustomerOrder; onPay: (invoiceName: string) => void }) {
	const stepIndex = STEPS.findIndex((s) => s.stage === o.stage);
	const showSteps = stepIndex >= 0 && isActive(o);
	return (
		<li className={`qo-order qo-order--${o.stage}`}>
			<div className="qo-order__head">
				<div>
					<div className="qo-order__id">{o.invoice_name}</div>
					<div className="qo-order__meta">
						{orderTypeLabel(o.order_type)} · {hhmm(o.creation)} · {money(o.amount, o.currency)}
					</div>
				</div>
				<span className={`qo-badge qo-badge--${o.stage}`}>{o.stage_label}</span>
			</div>

			{showSteps ? (
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

			{o.stage === "ready" && isActive(o) ? (
				<div className="qo-order__ready">Món đã sẵn sàng, mời {o.customer_name} đến quầy nhận.</div>
			) : null}

			<ul className="qo-order__items">
				{o.items.map((it, i) => {
					const opts = formatOptions(it.options, true);
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
					<button type="button" className="qo-btn qo-btn--primary qo-btn--sm" onClick={() => onPay(o.invoice_name)}>
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
}
