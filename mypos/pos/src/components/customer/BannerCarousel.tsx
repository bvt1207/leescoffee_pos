import { useEffect, useState } from "react";

/** Thời gian mỗi ảnh banner (giây) — một nơi duy nhất. */
export const BANNER_SECONDS = 5;

interface Props {
	banners: { title: string; image: string }[];
	/** Không có banner: hiện logo + tên thương hiệu (từ Branch). */
	brandName?: string;
	brandLogo?: string;
	variant?: "full" | "side";
}

/** Banner đổi ảnh mỗi BANNER_SECONDS giây, chuyển cảnh mờ dần; 1 ảnh thì đứng yên. Chỉ hiển thị, không thao tác. */
export default function BannerCarousel({ banners, brandName, brandLogo, variant = "full" }: Props) {
	const [index, setIndex] = useState(0);
	const count = banners.length;

	useEffect(() => {
		setIndex(0);
		if (count < 2) return;
		const timer = window.setInterval(() => setIndex((i) => (i + 1) % count), BANNER_SECONDS * 1000);
		return () => window.clearInterval(timer);
	}, [count]);

	// Tải trước ảnh kế tiếp để lần đổi không bị nháy trắng.
	useEffect(() => {
		if (count < 2) return;
		const img = new Image();
		img.src = banners[(index + 1) % count].image;
	}, [index, count, banners]);

	if (!count) {
		return (
			<div className={`pos-cd-banner pos-cd-banner--${variant} pos-cd-banner--brand`}>
				{brandLogo ? <img className="pos-cd-banner__logo" src={brandLogo} alt="" /> : null}
				{brandName ? <div className="pos-cd-banner__brand">{brandName}</div> : null}
			</div>
		);
	}

	return (
		<div className={`pos-cd-banner pos-cd-banner--${variant}`} aria-hidden="true">
			{banners.map((b, i) => (
				<img
					key={`${b.image}-${i}`}
					className={`pos-cd-banner__img${i === index ? " is-active" : ""}`}
					src={b.image}
					alt=""
					loading={i === 0 ? "eager" : "lazy"}
				/>
			))}
			{count > 1 ? (
				<div className="pos-cd-banner__dots">
					{banners.map((b, i) => (
						<span key={`${b.image}-dot-${i}`} className={`pos-cd-banner__dot${i === index ? " is-active" : ""}`} />
					))}
				</div>
			) : null}
		</div>
	);
}
