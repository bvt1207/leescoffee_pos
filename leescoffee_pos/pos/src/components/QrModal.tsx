import { useEffect } from "react";
import type { QrInfo } from "../types";
import { formatMoney } from "../store/cart";

interface Props {
	qr: QrInfo | null;
	currency?: string;
	onClose: () => void;
}

export default function QrModal({ qr, currency = "VND", onClose }: Props) {
	useEffect(() => {
		if (!qr) return;
		const handler = (event: KeyboardEvent) => {
			if (event.key === "Escape") onClose();
		};
		window.addEventListener("keydown", handler);
		return () => window.removeEventListener("keydown", handler);
	}, [qr, onClose]);

	if (!qr) return null;

	const copy = async () => {
		try {
			await navigator.clipboard.writeText(qr.payment_code);
		} catch {
			/* trình duyệt không hỗ trợ clipboard — bỏ qua */
		}
	};

	return (
		<div className="pos-modal-backdrop" onClick={onClose}>
			<div className="pos-modal" onClick={(event) => event.stopPropagation()}>
				<div className="pos-modal__header">
					<h3>Quét mã để thanh toán</h3>
					<button type="button" className="pos-modal__close" onClick={onClose}>
						×
					</button>
				</div>

				<div className="pos-modal__body">
					{qr.qr_url ? (
						<img className="pos-qr" src={qr.qr_url} alt="Mã QR thanh toán" />
					) : (
						<div className="pos-empty">Không lấy được ảnh mã QR.</div>
					)}

					<div className="pos-qr__amount">{formatMoney(qr.amount, currency)}</div>

					<div className="pos-qr__code">
						<span>Mã đơn: {qr.payment_code}</span>
						<button type="button" className="pos-btn pos-btn--ghost" onClick={copy}>
							Copy
						</button>
					</div>

					<p className="pos-modal__note">
						Đơn sẽ tự động được chuyển sang trạng thái đã thanh toán khi hệ thống ngân hàng
						xác nhận giao dịch.
					</p>
				</div>
			</div>
		</div>
	);
}
