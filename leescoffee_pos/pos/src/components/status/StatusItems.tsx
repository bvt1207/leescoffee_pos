import { useEffect, useLayoutEffect, useRef, useState } from "react";

/**
 * Món của một dòng màn /pos/status: "2× Cà Phê Sữa Đá · 1× Trà Đào", tối đa 2 dòng chữ (khung cao cố định 2 dòng).
 * Không vừa -> bớt món từ cuối cho tới khi vừa, thay bằng "+ N món" (N gồm cả món server không trả, `more`).
 * Đo lại khi danh sách món, bậc cỡ chữ (`tier`) hoặc kích thước cửa sổ đổi.
 */
export default function StatusItems({
	items,
	more,
	tier,
}: {
	items: Array<{ name: string; qty: number }>;
	more: number;
	tier: number;
}) {
	const ref = useRef<HTMLSpanElement>(null);
	const [resized, setResized] = useState(0);
	const sig = `${tier}#${resized}#${items.map((i) => `${i.qty}×${i.name}`).join("|")}`;
	const [fit, setFit] = useState({ sig, shown: items.length });
	const shown = fit.sig === sig ? fit.shown : items.length;

	useEffect(() => {
		const onResize = () => setResized((n) => n + 1);
		window.addEventListener("resize", onResize);
		return () => window.removeEventListener("resize", onResize);
	}, []);

	// Sau mỗi lần vẽ: tràn 2 dòng -> bớt một món, vẽ lại; vừa rồi thì ghi nhận (dừng).
	useLayoutEffect(() => {
		const el = ref.current;
		if (!el) return;
		if (shown > 0 && el.scrollHeight > el.clientHeight + 1) setFit({ sig, shown: shown - 1 });
		else if (fit.sig !== sig) setFit({ sig, shown });
	});

	const hidden = items.length - shown + more;
	if (!items.length && !more) return <span className="pos-sb-row__items" />;
	return (
		<span ref={ref} className="pos-sb-row__items">
			{items.slice(0, shown).map((it, i) => (
				<span key={`${it.name}-${i}`} className="pos-sb-item">
					{i > 0 ? <span className="pos-sb-item__sep"> · </span> : null}
					{it.qty}× {it.name}
				</span>
			))}
			{hidden > 0 ? (
				<span className="pos-sb-item pos-sb-item--more">
					{shown > 0 ? <span className="pos-sb-item__sep"> · </span> : null}+ {hidden} món
				</span>
			) : null}
		</span>
	);
}
