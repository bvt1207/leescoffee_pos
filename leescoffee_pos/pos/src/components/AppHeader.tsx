import { useEffect, useRef, useState } from "react";
import { NavLink } from "react-router-dom";
import { usePos } from "../lib/pos-context";
import { useSearch } from "../store/search";

export default function AppHeader() {
	const search = useSearch((s) => s.search);
	const onSearch = useSearch((s) => s.setSearch);
	const { config } = usePos();
	const brand = config?.brand;
	const user = (config as { user?: { full_name?: string; name?: string } } | null)?.user;
	const displayName = user?.full_name || user?.name || "";
	const initial = (displayName || "?").trim().slice(0, 1).toUpperCase();

	const [menuOpen, setMenuOpen] = useState(false);
	const menuRef = useRef<HTMLDivElement>(null);
	const searchRef = useRef<HTMLInputElement>(null);

	// Đóng dropdown khi bấm ra ngoài
	useEffect(() => {
		const onDown = (e: MouseEvent) => {
			if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
		};
		document.addEventListener("mousedown", onDown);
		return () => document.removeEventListener("mousedown", onDown);
	}, []);

	// Ctrl/Cmd + K để focus ô tìm
	useEffect(() => {
		const onKey = (e: KeyboardEvent) => {
			if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
				e.preventDefault();
				searchRef.current?.focus();
			}
		};
		document.addEventListener("keydown", onKey);
		return () => document.removeEventListener("keydown", onKey);
	}, []);

	const logout = async () => {
		try {
			await fetch("/api/method/logout", { method: "POST", credentials: "same-origin" });
		} finally {
			window.location.href = "/login?redirect-to=%2Fpos";
		}
	};

	const clearCache = () => {
		localStorage.clear();
		sessionStorage.clear();
		window.location.reload();
	};

	return (
		<header className="pos-header">
			<div className="pos-header__brand">
				{brand?.logo ? (
					<img className="pos-header__logo" src={brand.logo} alt={brand.name || "Logo"} />
				) : null}
				<div className="pos-header__titles">
					<div className="pos-header__name">{brand?.name || "POS"}</div>
					{brand?.address ? <div className="pos-header__sub">{brand.address}</div> : null}
				</div>
			</div>

			<div className="pos-header__search">
				<input
					ref={searchRef}
					type="search"
					className="pos-header__search-input"
					placeholder="Tìm món…"
					value={search}
					onChange={(e) => onSearch?.(e.target.value)}
					aria-label="Tìm món"
				/>
				<kbd className="pos-header__kbd">Ctrl K</kbd>
			</div>

			<div className="pos-header__right">
				<nav className="pos-header__nav">
					<NavLink to="/" end className="pos-navlink">Bán món</NavLink>
					<NavLink to="/orders" className="pos-navlink">Đơn hàng</NavLink>
				</nav>

				{displayName ? (
					<div className="pos-user" ref={menuRef}>
						<button
							type="button"
							className="pos-user__btn"
							aria-haspopup="menu"
							aria-expanded={menuOpen}
							onClick={() => setMenuOpen((v) => !v)}
						>
							<span className="pos-header__avatar">{initial}</span>
							<span className="pos-header__user-name">{displayName}</span>
							<span className="pos-user__chevron" aria-hidden>▾</span>
						</button>

						{menuOpen ? (
							<div className="pos-user__menu" role="menu">
								<div className="pos-user__info">
									<div className="pos-user__full">{displayName}</div>
									{user?.name && user.name !== displayName ? (
										<div className="pos-user__email">{user.name}</div>
									) : null}
								</div>
								<a className="pos-user__item" role="menuitem" href="/desk">Chuyển sang Desk</a>
								<button type="button" className="pos-user__item" role="menuitem" onClick={clearCache}>
									Xóa bộ nhớ đệm
								</button>
								<button type="button" className="pos-user__item pos-user__item--danger" role="menuitem" onClick={logout}>
									Đăng xuất
								</button>
							</div>
						) : null}
					</div>
				) : null}
			</div>
		</header>
	);
}