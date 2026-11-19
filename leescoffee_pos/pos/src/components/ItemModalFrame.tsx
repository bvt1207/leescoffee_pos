import { useEffect, useRef, type ReactNode } from "react";
import type { MenuItem } from "../types";

interface Props {
	item: MenuItem;
	/** Dòng nhỏ trên tên món, vd. "Chọn size". */
	hint: string;
	onClose: () => void;
	/** Thân cuộn được. */
	children: ReactNode;
}

/**
 * Khung bảng chọn món (hiện chỉ SizeModal dùng): đầu = ảnh + tên + nút đóng, thân cuộn. Esc / bấm nền để đóng, khóa cuộn trang khi mở.
 * Chỉ render khi mở (component cha quyết định).
 */
export default function ItemModalFrame({ item, hint, onClose, children }: Props) {
	const closeRef = useRef<HTMLButtonElement>(null);
	const name = item.name || item.item_name;
	// onClose của cha thường là hàm inline: giữ trong ref để effect chỉ chạy 1 lần khi mở
	// (không lấy lại focus nút đóng mỗi lần render).
	const onCloseRef = useRef(onClose);
	onCloseRef.current = onClose;

	useEffect(() => {
		const onKey = (event: KeyboardEvent) => {
			if (event.key === "Escape") onCloseRef.current();
		};
		window.addEventListener("keydown", onKey);
		const prevOverflow = document.body.style.overflow;
		document.body.style.overflow = "hidden";
		closeRef.current?.focus();
		return () => {
			window.removeEventListener("keydown", onKey);
			document.body.style.overflow = prevOverflow;
		};
	}, []);

	return (
		<div className="pos-modal-backdrop" onClick={onClose}>
			<div
				className="pos-modal pos-modal--item"
				role="dialog"
				aria-modal="true"
				aria-label={`${hint} ${name}`}
				onClick={(event) => event.stopPropagation()}
			>
				<div className="pos-size-head">
					{item.image ? (
						<img className="pos-size-head__img" src={item.image} alt="" />
					) : (
						<div className="pos-size-head__img pos-size-head__img--empty" aria-hidden>
							{name.slice(0, 1).toUpperCase()}
						</div>
					)}
					<div className="pos-size-head__text">
						<div className="pos-size-head__hint">{hint}</div>
						<h3 className="pos-size-head__name">{name}</h3>
					</div>
					<button
						ref={closeRef}
						type="button"
						className="pos-modal__close"
						aria-label="Đóng"
						onClick={onClose}
					>
						×
					</button>
				</div>

				<div className="pos-item-modal__body">{children}</div>
			</div>
		</div>
	);
}
