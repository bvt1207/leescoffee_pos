import { NavLink } from "react-router-dom";
import { usePos } from "../lib/pos-context";

export default function AppHeader() {
	const { config } = usePos();
	const brand = config?.brand;

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

			<nav className="pos-header__nav">
				<NavLink to="/" end className="pos-navlink">
					Bán món
				</NavLink>
				<NavLink to="/orders" className="pos-navlink">
					Đơn hàng
				</NavLink>
			</nav>
		</header>
	);
}
