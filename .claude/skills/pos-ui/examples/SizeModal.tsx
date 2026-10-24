import { useEffect, useRef } from "react";
import { formatMoney } from "../store/cart";
import { usePos } from "../lib/pos-context";
import type { MenuItem, MenuSize } from "../types";

interface Props {
	item: MenuItem;
	sizes: MenuSize[];
	open: boolean;
	onClose: () => void;
	onPick: (size: MenuSize) => void;
}

export default function SizeModal({ item, sizes, open, onClose, onPick }: Props) {
	const { config } = usePos();
	const currency = config?.profile?.currency || "VND";
	const closeRef = useRef<HTMLButtonElement>(null);

	useEffect(() => {
		if (!open) return;
		const onKey = (event: KeyboardEvent) => {
			if (event.key === "Escape") onClose();
		};
		window.addEventListener("keydown", onKey);
		const prevOverflow = document.body.style.overflow;
		document.body.style.overflow = "hidden";
		closeRef.current?.focus();
		return () => {
			window.removeEventListener("keydown", onKey);
			document.body.style.overflow = prevOverflow;
		};
	}, [open, onClose]);

	if (!open) return null;

	return (
		<div className="pos-modal-backdrop" onClick={onClose}>
			<div
				className="pos-modal pos-modal--size"
				role="dialog"
				aria-modal="true"
				aria-label={`Chọn size ${item.name}`}
				onClick={(event) => event.stopPropagation()}
			>
				<div className="pos-size-head">
					{item.image ? (
						<img className="pos-size-head__img" src={item.image} alt="" />
					) : (
						<div className="pos-size-head__img pos-size-head__img--empty" aria-hidden>
							{item.name.slice(0, 1).toUpperCase()}
						</div>
					)}
					<div className="pos-size-head__text">
						<div className="pos-size-head__hint">Chọn size</div>
						<h3 className="pos-size-head__name">{item.name}</h3>
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

				<div className="pos-size-body">
					{sizes.length ? (
						<div className="pos-size-list">
							{sizes.map((size) => {
								const disabled = size.rate == null;
								return (
									<button
										type="button"
										key={size.item_code}
										className={`pos-size-card${disabled ? " pos-size-card--disabled" : ""}`}
										disabled={disabled}
										onClick={() => onPick(size)}
									>
										<span className="pos-size-card__label">
											{size.label || size.item_code}
										</span>
										<span
											className={`pos-size-card__price${disabled ? " pos-size-card__price--none" : ""}`}
										>
											{disabled ? "Chưa có giá" : formatMoney(size.rate as number, currency)}
										</span>
									</button>
								);
							})}
						</div>
					) : (
						<div className="pos-empty">Món này chưa có size nào.</div>
					)}
				</div>
			</div>
		</div>
	);
}