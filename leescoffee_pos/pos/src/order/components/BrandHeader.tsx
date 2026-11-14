import type { Brand } from "../types";

/** Logo + tên quán lấy từ Branch (không hardcode). Thiếu logo -> chữ cái đầu của tên. */
export default function BrandHeader({ brand, compact = false }: { brand: Brand; compact?: boolean }) {
	const name = brand.name || "Đặt món";
	return (
		<div className={`qo-brand ${compact ? "qo-brand--compact" : ""}`}>
			{brand.logo ? (
				<img className="qo-brand__logo" src={brand.logo} alt="" />
			) : (
				<span className="qo-brand__mark" aria-hidden="true">
					{name.trim().charAt(0).toUpperCase()}
				</span>
			)}
			<div className="qo-brand__text">
				<div className="qo-brand__name">{name}</div>
				{!compact && brand.address ? <div className="qo-brand__sub">{brand.address}</div> : null}
			</div>
		</div>
	);
}
