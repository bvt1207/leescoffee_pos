import { useCallback, useEffect, useRef, useState, type PointerEvent } from "react";
import type { BannerImage } from "../types";

/** Thời gian mỗi ảnh banner trang /order (giây) — một nơi duy nhất. */
export const ORDER_BANNER_SECONDS = 5;
/** Vuốt ngang tối thiểu (px) để tính là chuyển ảnh. */
const SWIPE_PX = 40;

/**
 * Carousel ảnh MYPOS Banner ở đầu trang /order (dữ liệu: get_shop / get_me -> shop.banners).
 * - Khung cố định 16:9 (trang không giật khi ảnh tải xong), ảnh `contain` trên nền trơn -> không cắt chữ trong ảnh.
 * - Tự chuyển mỗi ORDER_BANNER_SECONDS giây; dừng khi chạm giữ / di chuột vào / tab ẩn; vuốt trái-phải để chuyển.
 * - Chỉ tải ảnh đang hiện + ảnh kế tiếp (tải trước); ảnh khác chỉ tải khi sắp tới lượt.
 * - prefers-reduced-motion: CSS bỏ hiệu ứng mờ dần, vẫn đổi ảnh.
 * - 1 ảnh: đứng yên, không chấm. 0 ảnh: không render (trang tự hiện khối thương hiệu).
 */
export default function OrderBanner({ banners }: { banners: BannerImage[] }) {
	const count = banners.length;
	const [index, setIndex] = useState(0);
	const [loaded, setLoaded] = useState<Record<number, boolean>>({});
	const [hold, setHold] = useState(false);
	const [hover, setHover] = useState(false);
	const [hidden, setHidden] = useState(() => typeof document !== "undefined" && document.hidden);
	// Ảnh đã được phép tải (đã hiện hoặc là ảnh kế tiếp). Ảnh xa hơn chưa render thẻ <img>.
	const [mounted, setMounted] = useState<Set<number>>(() => new Set([0, 1]));
	const startX = useRef<number | null>(null);

	// So theo danh sách ảnh (không theo tham chiếu mảng): get_me trả shop mới mỗi lần mở giỏ, không được nhảy về ảnh đầu.
	const sig = banners.map((b) => b.image).join("|");
	useEffect(() => {
		setIndex(0);
		setLoaded({});
		setMounted(new Set([0, 1]));
	}, [sig]);

	useEffect(() => {
		const onVis = () => setHidden(document.hidden);
		document.addEventListener("visibilitychange", onVis);
		return () => document.removeEventListener("visibilitychange", onVis);
	}, []);

	const go = useCallback(
		(next: number) => {
			if (count < 2) return;
			const i = ((next % count) + count) % count;
			setIndex(i);
			setMounted((m) => (m.has(i) && m.has((i + 1) % count) ? m : new Set([...m, i, (i + 1) % count])));
		},
		[count]
	);

	const paused = hold || hover || hidden;
	useEffect(() => {
		if (count < 2 || paused) return;
		const t = window.setTimeout(() => go(index + 1), ORDER_BANNER_SECONDS * 1000);
		return () => window.clearTimeout(t);
	}, [count, paused, index, go]);

	if (!count) return null;

	const onDown = (e: PointerEvent) => {
		startX.current = e.clientX;
		setHold(true);
	};
	const onUp = (e: PointerEvent) => {
		const from = startX.current;
		startX.current = null;
		setHold(false);
		if (from === null) return;
		const dx = e.clientX - from;
		if (Math.abs(dx) >= SWIPE_PX) go(index + (dx < 0 ? 1 : -1));
	};
	const onCancel = () => {
		startX.current = null;
		setHold(false);
	};

	return (
		<section
			className="qo-hero"
			aria-roledescription="carousel"
			aria-label="Ảnh giới thiệu của quán"
			onPointerDown={onDown}
			onPointerUp={onUp}
			onPointerCancel={onCancel}
			onPointerLeave={(e) => {
				if (e.pointerType === "mouse") setHover(false);
				if (startX.current !== null) onCancel();
			}}
			onPointerEnter={(e) => e.pointerType === "mouse" && setHover(true)}
		>
			<div className="qo-hero__frame">
				{!loaded[index] ? <span className="qo-skel qo-hero__skel" aria-hidden="true" /> : null}
				{banners.map((b, i) =>
					mounted.has(i) ? (
						<img
							key={`${b.image}-${i}`}
							className={`qo-hero__img${i === index && loaded[i] ? " is-on" : ""}`}
							src={b.image}
							alt={i === index ? b.title || "" : ""}
							aria-hidden={i !== index}
							draggable={false}
							decoding="async"
							// Ảnh đầu tiên tải ngay (nằm trên màn hình đầu); ảnh sau chỉ được mount khi sắp tới lượt.
							loading={i === 0 ? "eager" : "lazy"}
							onLoad={() => setLoaded((l) => (l[i] ? l : { ...l, [i]: true }))}
							onError={() => setLoaded((l) => (l[i] ? l : { ...l, [i]: true }))}
						/>
					) : null
				)}
			</div>
			{count > 1 ? (
				<div className="qo-hero__dots" aria-hidden="true">
					{banners.map((b, i) => (
						<span key={`${b.image}-dot-${i}`} className={`qo-hero__dot${i === index ? " is-on" : ""}`} />
					))}
				</div>
			) : null}
		</section>
	);
}
