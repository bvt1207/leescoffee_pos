import { useMemo, useState } from "react";
import { money } from "../format";
import type { Menu, MenuItem } from "../types";
import { IconClose, IconPlus, IconSearch } from "./icons";
import { MenuSkeleton } from "./Skeleton";

/** Danh sách món theo nhóm menu (chip cuộn ngang, dính đầu trang) + tìm kiếm. Bấm món -> ItemSheet. */
export default function MenuView({
	menus,
	currency,
	loading = false,
	onPick,
}: {
	menus: Menu[];
	currency: string;
	loading?: boolean;
	onPick: (item: MenuItem) => void;
}) {
	const [tab, setTab] = useState(0);
	const [query, setQuery] = useState("");

	const items = useMemo(() => {
		const q = query.trim().toLowerCase();
		if (q) return menus.flatMap((m) => m.items).filter((it) => it.name.toLowerCase().includes(q));
		return menus[tab]?.items || [];
	}, [menus, tab, query]);

	if (!loading && !menus.length) return <div className="qo-empty">Quán chưa có món nào để đặt.</div>;

	return (
		<section className="qo-menu">
			<div className="qo-menu__bar">
				<label className="qo-search">
					<IconSearch size={18} className="qo-search__icon" />
					<input
						className="qo-search__input"
						type="search"
						placeholder="Tìm món…"
						aria-label="Tìm món"
						value={query}
						onChange={(e) => setQuery(e.target.value)}
					/>
					{query ? (
						<button type="button" className="qo-search__clear" aria-label="Xóa tìm kiếm" onClick={() => setQuery("")}>
							<IconClose size={16} />
						</button>
					) : null}
				</label>
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
			</div>

			{loading ? (
				<MenuSkeleton />
			) : items.length ? (
				<div className="qo-grid">
					{items.map((it) => {
						const from = Math.min(...it.sizes.map((s) => s.rate));
						return (
							<button key={it.sizes[0].item_code} type="button" className="qo-card" onClick={() => onPick(it)}>
								<span className="qo-card__media">
									{it.image ? (
										<img className="qo-card__img" src={it.image} alt="" loading="lazy" decoding="async" />
									) : (
										<span className="qo-card__initial" aria-hidden="true">
											{it.name.charAt(0)}
										</span>
									)}
								</span>
								<span className="qo-card__body">
									<span className="qo-card__name">{it.name}</span>
									<span className="qo-card__foot">
										<span className="qo-card__price">
											{it.sizes.length > 1 ? <small>từ </small> : null}
											{money(from, currency)}
										</span>
										<span className="qo-card__add" aria-hidden="true">
											<IconPlus size={18} />
										</span>
									</span>
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
