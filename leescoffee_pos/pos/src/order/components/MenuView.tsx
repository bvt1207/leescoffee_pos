import { useMemo, useState } from "react";
import { money } from "../format";
import type { Menu, MenuItem } from "../types";

/** Danh sách món theo nhóm menu (tab cuộn ngang) + tìm kiếm. Bấm món -> ItemSheet. */
export default function MenuView({
	menus,
	currency,
	onPick,
}: {
	menus: Menu[];
	currency: string;
	onPick: (item: MenuItem) => void;
}) {
	const [tab, setTab] = useState(0);
	const [query, setQuery] = useState("");

	const items = useMemo(() => {
		const q = query.trim().toLowerCase();
		if (q) return menus.flatMap((m) => m.items).filter((it) => it.name.toLowerCase().includes(q));
		return menus[tab]?.items || [];
	}, [menus, tab, query]);

	if (!menus.length) return <div className="qo-empty">Quán chưa có món nào để đặt.</div>;

	return (
		<section className="qo-menu">
			<input
				className="qo-input qo-menu__search"
				type="search"
				placeholder="Tìm món…"
				aria-label="Tìm món"
				value={query}
				onChange={(e) => setQuery(e.target.value)}
			/>
			{!query && menus.length > 1 ? (
				<nav className="qo-tabs" aria-label="Nhóm món">
					{menus.map((m, i) => (
						<button
							key={m.name}
							type="button"
							className={`qo-tabs__btn ${i === tab ? "is-on" : ""}`}
							aria-current={i === tab}
							onClick={() => setTab(i)}
						>
							{m.menu_name || m.name}
						</button>
					))}
				</nav>
			) : null}

			{items.length ? (
				<div className="qo-grid">
					{items.map((it) => {
						const from = Math.min(...it.sizes.map((s) => s.rate));
						return (
							<button key={it.sizes[0].item_code} type="button" className="qo-card" onClick={() => onPick(it)}>
								{it.image ? (
									<img className="qo-card__img" src={it.image} alt="" loading="lazy" />
								) : (
									<span className="qo-card__img qo-card__img--empty" aria-hidden="true">
										{it.name.charAt(0)}
									</span>
								)}
								<span className="qo-card__name">{it.name}</span>
								<span className="qo-card__price">
									{it.sizes.length > 1 ? "từ " : ""}
									{money(from, currency)}
								</span>
								<span className="qo-card__add" aria-hidden="true">
									+
								</span>
							</button>
						);
					})}
				</div>
			) : (
				<div className="qo-empty">Không tìm thấy món phù hợp.</div>
			)}
		</section>
	);
}
