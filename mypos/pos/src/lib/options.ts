import type { CartOption, LineOption, OptionGroup } from "../types";

/**
 * Tùy chọn món động (MYPOS Option Group). Mọi tên nhóm / giá trị đến từ server,
 * frontend không biết "Đường", "Đá" hay "Topping" là gì.
 */

/** Lựa chọn mặc định khi thêm món: các giá trị is_default (Chọn 1 lấy giá trị đầu tiên). */
export function defaultOptions(groups: OptionGroup[] = []): CartOption[] {
	const out: CartOption[] = [];
	for (const g of groups) {
		const defs = g.values.filter((v) => v.is_default);
		const picked = g.selection_type === "Chọn 1" ? defs.slice(0, 1) : defs;
		for (const v of picked) out.push({ group: g.name, value: v.label });
	}
	return out;
}

/** Sắp theo thứ tự nhóm rồi thứ tự giá trị đã cấu hình; bỏ trùng và giá trị không còn thuộc nhóm. */
export function normalizeOptions(options: CartOption[], groups: OptionGroup[] = []): CartOption[] {
	const seen = new Set<string>();
	const out: CartOption[] = [];
	for (const g of groups) {
		for (const v of g.values) {
			const id = `${g.name}\u0000${v.label}`;
			if (seen.has(id)) continue;
			if (options.some((o) => o.group === g.name && o.value === v.label)) {
				seen.add(id);
				out.push({ group: g.name, value: v.label });
			}
		}
	}
	return out;
}

/** Khóa ổn định của tổ hợp tùy chọn (đã chuẩn hóa). */
export function optionsKey(options: CartOption[]): string {
	return options.map((o) => `${o.group}=${o.value}`).join(";");
}

export function isSelected(options: CartOption[], group: string, value: string): boolean {
	return options.some((o) => o.group === group && o.value === value);
}

/** Bấm chip: Chọn 1 = radio (nhóm không bắt buộc bấm lại để bỏ), Chọn nhiều = bật/tắt. */
export function toggleOption(options: CartOption[], group: OptionGroup, value: string): CartOption[] {
	const on = isSelected(options, group.name, value);
	if (group.selection_type === "Chọn 1") {
		const rest = options.filter((o) => o.group !== group.name);
		if (on) return group.required ? options : rest;
		return [...rest, { group: group.name, value }];
	}
	return on
		? options.filter((o) => !(o.group === group.name && o.value === value))
		: [...options, { group: group.name, value }];
}

/** Nhóm bắt buộc chưa chọn. */
export function missingRequired(options: CartOption[], groups: OptionGroup[] = []): OptionGroup[] {
	return groups.filter((g) => g.required && !options.some((o) => o.group === g.name));
}

// ---- Phụ thu (extra_price) — server là nguồn sự thật; hàm dưới chỉ để hiển thị ----

/** Phụ thu mỗi đơn vị của một giá trị theo cấu hình menu (0 nếu không có). */
export function valueSurcharge(groups: OptionGroup[] = [], group: string, value: string): number {
	const v = groups.find((g) => g.name === group)?.values.find((x) => x.label === value);
	return Math.max(0, Number(v?.extra_price) || 0);
}

/** Phụ thu mỗi đơn vị của dòng giỏ (ước tính từ menu, trước khi có preview). */
export function cartUnitSurcharge(options: CartOption[], groups: OptionGroup[] = []): number {
	return options.reduce((sum, o) => sum + valueSurcharge(groups, o.group, o.value), 0);
}

/** Phụ thu mỗi đơn vị của dòng đơn đã lưu (price snapshot server trả). */
export function lineUnitSurcharge(options?: LineOption[] | null): number {
	return (options || []).reduce((sum, o) => sum + Math.max(0, Number(o.price) || 0), 0);
}

/** "+10.000" (không đơn vị tiền) cho chip / chuỗi tùy chọn. */
export function plusPrice(amount: number): string {
	return `+${Math.round(amount).toLocaleString("vi-VN")}`;
}

/** Gom theo nhóm: [{title, values}] giữ thứ tự xuất hiện. */
function grouped(list: Array<{ title: string; value: string }>): Array<{ title: string; values: string[] }> {
	const out: Array<{ title: string; values: string[] }> = [];
	for (const it of list) {
		const hit = out.find((g) => g.title === it.title);
		if (hit) hit.values.push(it.value);
		else out.push({ title: it.title, values: [it.value] });
	}
	return out;
}

/** Từng nhóm thành một mẩu "Tên nhóm giá trị[, giá trị]" (dùng cho chip ở màn Pha chế).
 * withPrice: thêm " (+10.000)" sau giá trị có phụ thu (hóa đơn, chi tiết đơn, giỏ). */
export function optionParts(options?: LineOption[] | null, withPrice = false): string[] {
	const label = (o: LineOption) =>
		withPrice && Number(o.price) > 0 ? `${o.value} (${plusPrice(Number(o.price))})` : o.value;
	return grouped((options || []).map((o) => ({ title: o.group_title || "", value: label(o) })))
		.map((g) => `${g.title ? `${g.title} ` : ""}${g.values.join(", ")}`.trim())
		.filter(Boolean);
}

/** Chuỗi hiển thị cho dòng đơn: "Đường 70% · Đá 50% · Topping Trân châu, Thạch". Rỗng nếu không có. */
export function formatOptions(options?: LineOption[] | null, withPrice = false): string {
	return optionParts(options, withPrice).join(" · ");
}

/** Chuỗi tóm tắt cho dòng giỏ (dùng title từ option_groups của món). */
export function formatCartOptions(options: CartOption[], groups: OptionGroup[] = [], withPrice = false): string {
	const title = (name: string) => groups.find((g) => g.name === name)?.title || "";
	return formatOptions(
		options.map((o) => ({
			group: o.group,
			group_title: title(o.group),
			value: o.value,
			price: valueSurcharge(groups, o.group, o.value),
		})),
		withPrice
	);
}
