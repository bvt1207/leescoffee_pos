import type { OrderTypeValue } from "../types";

const CHOICES: Array<{ value: OrderTypeValue; title: string; sub: string }> = [
	{ value: "Take Away", title: "Mang đi", sub: "Nhận món tại quầy rồi mang đi" },
	{ value: "Dine In", title: "Tại quán", sub: "Dùng tại quán, nhận món tại quầy khi được báo" },
];

/** Chọn loại đơn. variant "cards" = bước đầu sau đăng nhập; "segmented" = đổi nhanh trong giỏ. */
export default function OrderTypePicker({
	value,
	onChange,
	variant = "cards",
}: {
	value?: OrderTypeValue;
	onChange: (v: OrderTypeValue) => void;
	variant?: "cards" | "segmented";
}) {
	if (variant === "segmented") {
		return (
			<div className="qo-segmented" role="radiogroup" aria-label="Loại đơn">
				{CHOICES.map((c) => (
					<button
						key={c.value}
						type="button"
						role="radio"
						aria-checked={value === c.value}
						className={`qo-segmented__btn ${value === c.value ? "is-on" : ""}`}
						onClick={() => onChange(c.value)}
					>
						{c.title}
					</button>
				))}
			</div>
		);
	}
	return (
		<section className="qo-type">
			<h1 className="qo-type__title">Bạn dùng món ở đâu?</h1>
			<div className="qo-type__grid" role="radiogroup" aria-label="Loại đơn">
				{CHOICES.map((c) => (
					<button
						key={c.value}
						type="button"
						role="radio"
						aria-checked={value === c.value}
						className={`qo-type__card qo-type__card--${c.value === "Take Away" ? "takeaway" : "dinein"}`}
						onClick={() => onChange(c.value)}
					>
						<span className="qo-type__name">{c.title}</span>
						<span className="qo-type__sub">{c.sub}</span>
					</button>
				))}
			</div>
		</section>
	);
}
