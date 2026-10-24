import { useMemo, useState } from "react";
import { usePos } from "../lib/pos-context";
import { useCart } from "../store/cart";
import type { MenuItem, MenuSize } from "../types";
import SizeModal from "./SizeModal";

function MenuCard({ item }: { item: MenuItem }) {
	const sizes = item.sizes || [];
	// Món 1 size: label rỗng -> thêm thẳng giỏ, không mở modal.
	const isSingle = sizes.length === 1 && !sizes[0].label;
	const add = useCart((state) => state.addVariant);
	const [open, setOpen] = useState(false);

	const codes = useMemo(() => sizes.map((s) => s.item_code), [sizes]);
	const qty = useCart((state) =>
		state.lines
			.filter((line) => codes.includes(line.item_code))
			.reduce((sum, line) => sum + line.qty, 0)
	);

	const addSize = (size: MenuSize) => {
		if (size.rate == null) return; // chưa có giá: không chọn được
		add({
			item_code: size.item_code,
			item_name: item.name,
			item_type: "",
			price: size.rate,
			size: size.label || null,
		});
	};

	const handleClick = () => {
		if (isSingle) addSize(sizes[0]);
		else setOpen(true);
	};

	// Món 1 size chưa có giá: làm mờ, không bấm được.
	const unavailable = isSingle && sizes[0].rate == null;

	return (
		<>
			<button
				type="button"
				className="pos-menu-card"
				onClick={handleClick}
				disabled={unavailable}
			>
				<div className="pos-menu-card__media">
					{item.image ? (
						<img src={item.image} alt="" loading="lazy" />
					) : (
						<span className="pos-menu-card__placeholder" aria-hidden>
							{item.name.slice(0, 1).toUpperCase()}
						</span>
					)}
					{!isSingle ? (
						<span className="pos-menu-card__chip">{sizes.length} size</span>
					) : null}
					{qty > 0 ? <span className="pos-menu-card__qty">x{qty}</span> : null}
				</div>
				<span className="pos-menu-card__name">{item.name}</span>
			</button>

			{!isSingle ? (
				<SizeModal
					item={item}
					sizes={sizes}
					open={open}
					onClose={() => setOpen(false)}
					onPick={(size) => {
						setOpen(false);
						addSize(size);
					}}
				/>
			) : null}
		</>
	);
}

export default function MenuGrid({ search = "" }: { search?: string }) {
	const { menus } = usePos();
	const [group, setGroup] = useState<string>("all");

	const items = useMemo(() => {
		const q = search.trim().toLowerCase();
		return menus
			.filter((g) => group === "all" || g.name === group)
			.flatMap((g) => (g.items || []).map((it) => ({ gid: g.name, it })))
			.filter(({ it }) => !q || it.name.toLowerCase().includes(q));
	}, [menus, group, search]);

	if (!menus.length) {
		return <div className="pos-empty">Chưa có menu nào được cấu hình.</div>;
	}

	return (
		<div className="pos-menu">
			{menus.length > 1 ? (
				<div className="pos-chips" role="tablist">
					<button
						type="button"
						className={`pos-chip ${group === "all" ? "is-active" : ""}`}
						onClick={() => setGroup("all")}
					>
						Tất cả
					</button>
					{menus.map((g) => (
						<button
							key={g.name}
							type="button"
							className={`pos-chip ${group === g.name ? "is-active" : ""}`}
							onClick={() => setGroup(g.name)}
						>
							{g.menu_name || g.name}
						</button>
					))}
				</div>
			) : null}

			{items.length ? (
				<div className="pos-menu-grid">
					{items.map(({ gid, it }) => (
						<MenuCard key={`${gid}-${it.name}`} item={it} />
					))}
				</div>
			) : (
				<div className="pos-empty">Không tìm thấy món phù hợp.</div>
			)}
		</div>
	);
}