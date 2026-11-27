import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { OrderStatusEntry } from "../../types";

export type BoardEntry = OrderStatusEntry & { key: string };

/**
 * Bậc cỡ chữ: chiều cao một dòng theo % chiều cao màn (vh). Bậc cuối là nhỏ nhất vẫn đọc được từ xa
 * (mã ≈ 40px ở 1080p). CSS `.pos-sb-col--t0/1/2` đặt cỡ chữ tương ứng (styles/status-board.css).
 */
const ROW_VH: Record<"preparing" | "ready", number[]> = {
	preparing: [9, 7, 5.6],
	ready: [11, 8.5, 6.5],
};
/** Khoảng cách giữa các dòng (vh) — khớp `gap` của `.pos-sb-col__list`. */
const GAP_VH = 0.8;
/** Thời gian mờ dần của dòng vừa rời khỏi màn (ms). */
export const LEAVE_MS = 260;

const reduceMotion = () =>
	typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/**
 * Một cột của màn theo dõi đơn. Không cuộn: chọn bậc chữ lớn nhất chứa hết số đơn; không đủ chỗ ở bậc nhỏ nhất
 * -> hiện vừa chỗ + dòng "+ N đơn nữa" (N gồm cả số đơn server không trả chi tiết).
 * Dòng rời khỏi màn (không còn ở cột nào) được giữ LEAVE_MS để mờ dần.
 */
export default function StatusColumn({
	variant,
	title,
	emptyText,
	items,
	more,
	boardKeys,
}: {
	variant: "preparing" | "ready";
	title: string;
	emptyText: string;
	items: BoardEntry[];
	more: number;
	/** Khóa của mọi đơn đang hiện trên cả màn: đơn chuyển sang cột kia không bị coi là "rời đi". */
	boardKeys: Set<string>;
}) {
	const listRef = useRef<HTMLOListElement>(null);
	const [height, setHeight] = useState(0);
	const [ghosts, setGhosts] = useState<Array<{ entry: BoardEntry; index: number }>>([]);
	const prev = useRef<BoardEntry[]>(items);

	useLayoutEffect(() => {
		const el = listRef.current;
		if (!el) return;
		const measure = () => setHeight(el.clientHeight);
		measure();
		const ro = new ResizeObserver(measure);
		ro.observe(el);
		return () => ro.disconnect();
	}, []);

	// Dòng biến mất khỏi cả màn (Đã hoàn thành...) -> giữ tạm để mờ dần.
	useEffect(() => {
		const before = prev.current;
		prev.current = items;
		if (reduceMotion()) return;
		const gone = before
			.map((entry, index) => ({ entry, index }))
			.filter(({ entry }) => !boardKeys.has(entry.key));
		if (!gone.length) return;
		setGhosts((g) => [...g, ...gone]);
		// Không hủy hẹn giờ khi danh sách đổi tiếp trong lúc mờ dần (nếu hủy, dòng ma sẽ kẹt lại).
		window.setTimeout(
			() => setGhosts((g) => g.filter((x) => !gone.some((y) => y.entry.key === x.entry.key))),
			LEAVE_MS
		);
	}, [items, boardKeys]);

	const total = items.length + more;
	const vh = window.innerHeight / 100;
	const tiers = ROW_VH[variant];
	const capacity = (rowVh: number) =>
		height > 0 ? Math.max(1, Math.floor((height + GAP_VH * vh) / ((rowVh + GAP_VH) * vh))) : total;
	let tier = tiers.findIndex((rowVh) => total <= capacity(rowVh));
	let shown = items;
	let hidden = more;
	if (tier < 0) {
		tier = tiers.length - 1;
		const fit = Math.max(0, capacity(tiers[tier]) - 1); // chừa một dòng cho "+ N đơn nữa"
		shown = items.slice(0, fit);
		hidden = total - shown.length;
	}

	// Chèn dòng đang rời đi vào đúng vị trí cũ (chỉ khi còn chỗ hiển thị).
	const rows: Array<{ entry: BoardEntry; leaving: boolean }> = shown.map((entry) => ({ entry, leaving: false }));
	for (const g of ghosts) {
		if (g.index <= rows.length) rows.splice(g.index, 0, { entry: g.entry, leaving: true });
	}

	return (
		<section className={`pos-sb-col pos-sb-col--${variant} pos-sb-col--t${tier}`} aria-label={title}>
			<header className="pos-sb-col__head">
				<h2 className="pos-sb-col__title">{title}</h2>
				<span className="pos-sb-col__count">{total}</span>
			</header>
			<ol ref={listRef} className="pos-sb-col__list">
				{rows.map(({ entry, leaving }) => (
					<li
						key={`${entry.key}${leaving ? ":out" : ""}`}
						data-sb-key={leaving ? undefined : entry.key}
						className={`pos-sb-row${leaving ? " is-leaving" : ""}`}
					>
						<span className="pos-sb-row__code">{entry.code}</span>
						<span className="pos-sb-row__info">
							{/* Luôn có ô tên (trống khi không có tên) để mọi dòng cùng bố cục: tên trên, loại đơn dưới. */}
							<span className="pos-sb-row__name">{entry.name}</span>
							<span className="pos-sb-row__label">{entry.label}</span>
						</span>
					</li>
				))}
				{hidden > 0 && shown.length < total ? <li className="pos-sb-more">+ {hidden} đơn nữa</li> : null}
				{!total && !ghosts.length ? <li className="pos-sb-empty">{emptyText}</li> : null}
			</ol>
		</section>
	);
}
