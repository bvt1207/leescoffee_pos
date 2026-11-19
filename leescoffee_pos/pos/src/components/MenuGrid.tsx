import { useMemo, useState } from "react";
import { defaultOptions } from "../lib/options";
import { usePos } from "../lib/pos-context";
import { useCart } from "../store/cart";
import { ALL_GROUPS, NO_GROUP, useMenuFilter } from "../store/menuFilter";
import { useSearch } from "../store/search";
import type { CartOption, MenuItem, MenuSize } from "../types";
import OptionModal from "./OptionModal";
import SizeModal from "./SizeModal";

const itemName = (item: MenuItem) => item.name || item.item_name || item.item_code || "";
const groupKey = (item: MenuItem) => item.item_group || NO_GROUP;

function MenuCard({ item }: { item: MenuItem }) {
	const sizes = item.sizes || [];
	const groups = item.option_groups || [];
	const name = itemName(item);
	// Món 1 size: label rỗng -> không mở SizeModal.
	const isSingle = sizes.length === 1 && !sizes[0].label;
	const hasOptions = groups.length > 0;
	const add = useCart((state) => state.addVariant);
	const [open, setOpen] = useState(false);

	const codes = useMemo(() => sizes.map((s) => s.item_code), [sizes]);
	const qty = useCart((state) =>
		state.lines
			.filter((line) => codes.includes(line.item_code))
			.reduce((sum, line) => sum + line.qty, 0)
	);

	const addSize = (size: MenuSize, options?: CartOption[]) => {
		if (size.rate == null) return; // chưa có giá: không chọn được
		// Tùy chọn: dùng option_groups của món (variant kế thừa template); mặc định nếu chưa chọn.
		add({
			item_code: size.item_code,
			item_name: name,
			item_type: "",
			price: size.rate,
			size: size.label || null,
			option_groups: groups,
			options: options ?? defaultOptions(groups),
		});
	};

	// Nhiều size -> SizeModal; 1 size có tùy chọn -> OptionModal; 1 size không tùy chọn -> thêm thẳng.
	const handleClick = () => {
		if (isSingle && !hasOptions) addSize(sizes[0]);
		else setOpen(true);
	};

	// Món 1 size chưa có giá: làm mờ, không bấm được.
	const unavailable = isSingle && sizes[0].rate == null;
	const hasChoices = !isSingle || hasOptions;

	return (
		<>
			<button
				type="button"
				className="pos-menu-card"
				onClick={handleClick}
				disabled={unavailable}
				title={name}
			>
				<span className="pos-menu-card__media">
					{item.image ? (
						<img src={item.image} alt="" loading="lazy" decoding="async" />
					) : (
						<span className="pos-menu-card__placeholder" aria-hidden>
							{name.slice(0, 1).toUpperCase()}
						</span>
					)}
					{hasChoices ? (
						<span
							className="pos-menu-card__dot"
							role="img"
							aria-label={isSingle ? "Có tùy chọn" : "Có size"}
						/>
					) : null}
					{qty > 0 ? <span className="pos-menu-card__qty">x{qty}</span> : null}
				</span>
				<span className="pos-menu-card__name">{name}</span>
			</button>

			{open && !isSingle ? (
				<SizeModal
					item={item}
					sizes={sizes}
					open
					onClose={() => setOpen(false)}
					onPick={(size) => {
						setOpen(false);
						addSize(size);
					}}
				/>
			) : null}

			{open && isSingle && hasOptions ? (
				<OptionModal
					item={item}
					size={sizes[0]}
					onClose={() => setOpen(false)}
					onAdd={(options) => {
						setOpen(false);
						addSize(sizes[0], options);
					}}
				/>
			) : null}
		</>
	);
}

export default function MenuGrid({ search = "" }: { search?: string }) {
	const { menus } = usePos();
	const group = useMenuFilter((state) => state.group);
	const setGroup = useMenuFilter((state) => state.setGroup);
	const setSearch = useSearch((state) => state.setSearch);

	// Mọi món của mọi menu, giữ thứ tự cấu hình.
	const all = useMemo(
		() => menus.flatMap((m) => (m.items || []).map((it) => ({ key: `${m.name}-${itemName(it)}`, it }))),
		[menus]
	);

	// Tab = Item Group theo thứ tự xuất hiện trong menu; "Khác" (món không có nhóm) luôn cuối.
	// Chỉ sinh từ món có thật nên không có tab rỗng.
	const tabs = useMemo(() => {
		const seen: string[] = [];
		for (const { it } of all) {
			const k = groupKey(it);
			if (k !== NO_GROUP && !seen.includes(k)) seen.push(k);
		}
		if (all.some(({ it }) => groupKey(it) === NO_GROUP)) seen.push(NO_GROUP);
		return seen;
	}, [all]);

	const q = search.trim().toLowerCase();
	// Tab đã nhớ không còn trong menu -> coi như "Tất cả". Đang tìm -> tìm trên toàn bộ món.
	const activeGroup = q || !tabs.includes(group) ? ALL_GROUPS : group;
	const showTabs = tabs.length > 1;

	const items = useMemo(
		() =>
			all.filter(
				({ it }) =>
					(activeGroup === ALL_GROUPS || groupKey(it) === activeGroup) &&
					(!q || itemName(it).toLowerCase().includes(q))
			),
		[all, activeGroup, q]
	);

	if (!menus.length) {
		return <div className="pos-empty">Chưa có menu nào được cấu hình.</div>;
	}

	const tab = (key: string, label: string) => (
		<button
			key={key}
			type="button"
			role="tab"
			aria-selected={activeGroup === key}
			className={`pos-menu-tab${activeGroup === key ? " is-active" : ""}`}
			onClick={() => {
				// Bấm tab khi đang tìm: bỏ từ khóa để tab có tác dụng ngay.
				if (q) setSearch("");
				setGroup(key);
			}}
		>
			{label}
		</button>
	);

	return (
		<div className="pos-menu">
			{showTabs ? (
				<div className="pos-menu-tabs" role="tablist" aria-label="Nhóm món">
					{tab(ALL_GROUPS, "Tất cả")}
					{tabs.map((k) => tab(k, k === NO_GROUP ? "Khác" : k))}
				</div>
			) : null}

			{items.length ? (
				<div className="pos-menu-grid">
					{items.map(({ key, it }) => (
						<MenuCard key={key} item={it} />
					))}
				</div>
			) : (
				<div className="pos-empty">Không tìm thấy món phù hợp.</div>
			)}
		</div>
	);
}
