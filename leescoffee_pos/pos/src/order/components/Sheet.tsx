import { useEffect, useRef, type ReactNode } from "react";

/** Bottom sheet (mobile) / hộp giữa màn (màn rộng). Esc + bấm nền để đóng, khóa cuộn nền. */
export default function Sheet({
	title,
	onClose,
	children,
	footer,
	labelledBy = "qo-sheet-title",
}: {
	title: string;
	onClose: () => void;
	children: ReactNode;
	footer?: ReactNode;
	labelledBy?: string;
}) {
	const panel = useRef<HTMLDivElement>(null);

	useEffect(() => {
		const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
		document.addEventListener("keydown", onKey);
		document.body.classList.add("qo-no-scroll");
		panel.current?.focus();
		return () => {
			document.removeEventListener("keydown", onKey);
			document.body.classList.remove("qo-no-scroll");
		};
	}, [onClose]);

	return (
		<div className="qo-overlay" onClick={onClose}>
			<div
				ref={panel}
				className="qo-sheet"
				role="dialog"
				aria-modal="true"
				aria-labelledby={labelledBy}
				tabIndex={-1}
				onClick={(e) => e.stopPropagation()}
			>
				<header className="qo-sheet__head">
					<h2 id={labelledBy} className="qo-sheet__title">
						{title}
					</h2>
					<button type="button" className="qo-icon-btn" aria-label="Đóng" onClick={onClose}>
						×
					</button>
				</header>
				<div className="qo-sheet__body">{children}</div>
				{footer ? <footer className="qo-sheet__foot">{footer}</footer> : null}
			</div>
		</div>
	);
}
