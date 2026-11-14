import { useCallback, useEffect, useRef, useState } from "react";
import { errorText, OrderApiError, orderApi } from "../api";
import { clock, money, orderTypeLabel } from "../format";
import { usePolling } from "../poll";
import type { CustomerOrder, PaymentQr } from "../types";

const POLL_MS = 3000;

/**
 * Màn chuyển khoản: hiện VietQR + số tiền + nội dung, đếm ngược hạn thanh toán (giây do server
 * tính), tự kiểm tra trạng thái đơn mỗi 3 giây. Webhook SePay xác nhận -> đơn chuyển "Chưa làm".
 */
export default function PaymentView({
	token,
	invoiceName,
	onPaid,
	onBack,
	onSessionExpired,
}: {
	token: string;
	invoiceName: string;
	onPaid: (o: CustomerOrder) => void;
	onBack: () => void;
	onSessionExpired: () => void;
}) {
	const [qr, setQr] = useState<PaymentQr | null>(null);
	const [order, setOrder] = useState<CustomerOrder | null>(null);
	const [left, setLeft] = useState<number | null>(null);
	const [error, setError] = useState("");
	const [copied, setCopied] = useState(false);
	const deadline = useRef(0);
	const paidRef = useRef(false);

	const fail = useCallback(
		(err: unknown) => {
			if (err instanceof OrderApiError && err.sessionExpired) onSessionExpired();
			else setError(errorText(err));
		},
		[onSessionExpired]
	);

	// Sinh (hoặc lấy lại — idempotent) mã QR. Unmount (về menu) -> abort.
	useEffect(() => {
		const ctrl = new AbortController();
		(async () => {
			try {
				const [q, o] = await Promise.all([
					orderApi.createPaymentQr(token, invoiceName),
					orderApi.getOrder(token, invoiceName, ctrl.signal),
				]);
				if (ctrl.signal.aborted) return;
				setQr(q);
				setOrder(o);
				deadline.current = Date.now() + q.expires_in * 1000;
				setLeft(q.expires_in);
			} catch (err) {
				if (!ctrl.signal.aborted) fail(err);
			}
		})();
		return () => ctrl.abort();
	}, [token, invoiceName, fail]);

	const expired = order?.stage === "expired" || left === 0;
	const waiting = !!qr && !expired && !paidRef.current;

	// Đếm ngược (mốc = thời điểm nhận + expires_in của server). Dừng khi hết hạn.
	useEffect(() => {
		if (!waiting) return;
		const t = window.setInterval(() => {
			setLeft(Math.max(0, Math.round((deadline.current - Date.now()) / 1000)));
		}, 1000);
		return () => window.clearInterval(t);
	}, [waiting]);

	// Kiểm tra đã thanh toán: 1 chuỗi poll (không chồng request), dừng khi tab ẩn / hết hạn / đã trả,
	// giãn nhịp khi lỗi. Lỗi phiên -> về đăng nhập (throw để usePolling tính backoff cho lỗi khác).
	usePolling(
		async (signal) => {
			try {
				const o = await orderApi.getOrder(token, invoiceName, signal);
				if (signal.aborted) return;
				setOrder(o);
				setError("");
				if (o.stage !== "awaiting_payment" && o.stage !== "expired" && !paidRef.current) {
					paidRef.current = true;
					onPaid(o);
				}
			} catch (err) {
				if (signal.aborted || (err instanceof OrderApiError && err.aborted)) return;
				fail(err);
				throw err;
			}
		},
		waiting,
		POLL_MS,
		{ immediate: false }
	);

	const copy = async () => {
		if (!qr) return;
		try {
			await navigator.clipboard.writeText(qr.payment_code);
			setCopied(true);
			window.setTimeout(() => setCopied(false), 2000);
		} catch {
			/* trình duyệt chặn clipboard: khách tự chọn chữ */
		}
	};

	return (
		<main className="qo-pay">
			<button type="button" className="qo-link qo-pay__back" onClick={onBack}>
				← Về menu
			</button>
			<h1 className="qo-pay__title">Chuyển khoản để hoàn tất</h1>
			{order ? (
				<p className="qo-pay__sub">
					Đơn {order.invoice_name} · {orderTypeLabel(order.order_type)} · {order.customer_name}
				</p>
			) : null}

			{error ? (
				<div className="qo-alert qo-alert--error" role="alert">
					{error}
				</div>
			) : null}

			{expired ? (
				<div className="qo-pay__expired" role="status">
					<strong>Đơn đã hết hạn thanh toán.</strong>
					<span>Nếu bạn đã chuyển khoản, vui lòng báo nhân viên tại quầy kèm mã đơn. Nếu chưa, hãy đặt lại.</span>
					<button type="button" className="qo-btn qo-btn--primary" onClick={onBack}>
						Đặt lại
					</button>
				</div>
			) : qr ? (
				<div className="qo-pay__card">
					{qr.qr_url ? (
						<img className="qo-pay__qr" src={qr.qr_url} alt="Mã QR chuyển khoản" referrerPolicy="no-referrer" />
					) : null}
					<div className="qo-pay__amount">{money(qr.amount, order?.currency || "VND")}</div>
					<div className="qo-pay__code">
						<span className="qo-pay__code-label">Nội dung chuyển khoản</span>
						<code className="qo-pay__code-value">{qr.payment_code}</code>
						<button type="button" className="qo-btn qo-btn--ghost qo-btn--sm" onClick={copy}>
							{copied ? "Đã chép" : "Chép"}
						</button>
					</div>
					<p className="qo-fine">
						Quét bằng app ngân hàng. Giữ nguyên số tiền và nội dung để đơn được xác nhận tự động.
					</p>
					<div className="qo-pay__wait" aria-live="polite">
						<span className="qo-spinner" aria-hidden="true" />
						Đang chờ thanh toán… còn {left !== null ? clock(left) : "--:--"}
					</div>
				</div>
			) : !error ? (
				<div className="qo-pay__wait">
					<span className="qo-spinner" aria-hidden="true" />
					Đang tạo mã QR…
				</div>
			) : null}
		</main>
	);
}
