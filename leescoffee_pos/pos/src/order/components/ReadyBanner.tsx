import type { CustomerOrder } from "../types";

/** Banner nổi khi pha chế bấm "Đã làm". Ở lại tới khi khách bấm "Đã hiểu". */
export default function ReadyBanner({ order, onDismiss }: { order: CustomerOrder; onDismiss: () => void }) {
	return (
		<div className="qo-ready" role="alertdialog" aria-live="assertive" aria-labelledby="qo-ready-title">
			<div className="qo-ready__icon" aria-hidden="true">
				✓
			</div>
			<div className="qo-ready__text">
				<strong id="qo-ready-title">Món của bạn đã sẵn sàng, mời đến quầy nhận</strong>
				<span>
					Đơn {order.invoice_name} · {order.customer_name}
				</span>
			</div>
			<button type="button" className="qo-btn qo-btn--light" onClick={onDismiss}>
				Đã hiểu
			</button>
		</div>
	);
}
