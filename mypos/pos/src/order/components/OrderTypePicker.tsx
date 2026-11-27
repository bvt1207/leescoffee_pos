import type { ComponentType } from "react";
import type { OrderTypeValue } from "../types";
import { IconBag, IconChevronRight, IconCup, IconReceipt } from "./icons";

const CHOICES: Array<{ value: OrderTypeValue; title: string; sub: string; Icon: ComponentType<{ size?: number }> }> = [
	{ value: "Take Away", title: "Mang đi", sub: "Nhận món tại quầy rồi mang đi", Icon: IconBag },
	{ value: "Dine In", title: "Tại quán", sub: "Dùng tại quán, nhận món tại quầy khi được báo", Icon: IconCup },
];

/** Chọn loại đơn.
 *  - "cards": bước đầu sau đăng nhập (lời chào + 2 lựa chọn lớn + lối vào "Đơn của tôi").
 *  - "segmented": đổi nhanh trong giỏ. "compact": công tắc nhỏ ở dải phụ của màn menu. */
export default function OrderTypePicker({
	value,
	onChange,
	variant = "cards",
	greetingName,
	activeOrders = 0,
	onOpenOrders,
}: {
	value?: OrderTypeValue;
	onChange: (v: OrderTypeValue) => void;
	variant?: "cards" | "segmented" | "compact";
	greetingName?: string;
	activeOrders?: number;
	onOpenOrders?: () => void;
}) {
	if (variant !== "cards") {
		return (
			<div
				className={`qo-segmented ${variant === "compact" ? "qo-segmented--compact" : ""}`}
				role="radiogroup"
				aria-label="Loại đơn"
			>
				{CHOICES.map((c) => (
					<button
						key={c.value}
						type="button"
						role="radio"
						aria-checked={value === c.value}
						className={`qo-segmented__btn ${value === c.value ? "is-on" : ""}`}
						onClick={() => onChange(c.value)}
					>
						{variant === "compact" ? <c.Icon size={16} /> : null}
						{c.title}
					</button>
				))}
			</div>
		);
	}
	return (
		<section className="qo-type">
			{greetingName ? <p className="qo-type__hello">Chào {greetingName},</p> : null}
			<h1 className="qo-type__title">Bạn dùng món ở đâu?</h1>
			<div className="qo-type__grid" role="radiogroup" aria-label="Loại đơn">
				{CHOICES.map((c) => (
					<button
						key={c.value}
						type="button"
						role="radio"
						aria-checked={value === c.value}
						className="qo-type__card"
						onClick={() => onChange(c.value)}
					>
						<span className="qo-type__icon">
							<c.Icon size={28} />
						</span>
						<span className="qo-type__name">{c.title}</span>
						<span className="qo-type__sub">{c.sub}</span>
					</button>
				))}
			</div>
			{onOpenOrders ? (
				<button type="button" className="qo-rowlink" onClick={onOpenOrders}>
					<IconReceipt />
					<span className="qo-rowlink__text">Đơn của tôi</span>
					{activeOrders ? <span className="qo-pill">{activeOrders} đang xử lý</span> : null}
					<IconChevronRight className="qo-rowlink__chev" />
				</button>
			) : null}
		</section>
	);
}
