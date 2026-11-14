import type { OrderType } from "../types";

/** Chữ hiển thị loại đơn (dùng chung Orders / Kitchen). */
export const typeLabel = (t: string) => (t === "Take Away" ? "Mang đi" : "Tại quán");

/** Hậu tố modifier theo loại đơn: "takeaway" | "dinein" (màu lấy từ token --pos-takeaway-* / --pos-dinein-*). */
export const typeModifier = (t: string) => (t === "Take Away" ? "takeaway" : "dinein");

/** Đơn khách tự đặt qua web QR (không có thẻ rung). */
export const isQrOrder = (channel?: string | null) => channel === "QR";

/** Chip kênh "QR" (token --pos-qr-*); kênh POS không hiện gì. */
export function ChannelChip({ channel }: { channel?: string | null }) {
	return isQrOrder(channel) ? (
		<span className="pos-tag pos-tag--qr" title="Khách tự đặt qua mã QR">
			QR
		</span>
	) : null;
}

/** Chip loại đơn: màu riêng cho Mang đi / Tại quán, khác màu trạng thái (cảnh báo, thương hiệu). */
export default function OrderTypeChip({ type }: { type: OrderType | string }) {
	return <span className={`pos-tag pos-tag--${typeModifier(type)}`}>{typeLabel(type)}</span>;
}
