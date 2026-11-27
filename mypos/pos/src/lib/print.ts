/**
 * In bằng window.print() với khổ giấy riêng cho từng lần in.
 *
 * `@page { size }` không nhận var(), nên chèn tạm một thẻ <style> chứa khổ giấy,
 * gắn class lên <body> để CSS @media print biết đang in gì, rồi gỡ cả hai
 * khi sự kiện afterprint xảy ra.
 *
 * Lưu ý: afterprint xảy ra khi hộp thoại in đóng, kể cả khi người dùng bấm Hủy.
 */
export function cssVar(name: string, fallback: string): string {
	const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
	return value || fallback;
}

export function printWithPage(
	size: string,
	opts: { bodyClass?: string; onAfter?: () => void } = {}
): void {
	const style = document.createElement("style");
	style.textContent = `@page { size: ${size}; margin: 0; }`;
	document.head.appendChild(style);
	if (opts.bodyClass) document.body.classList.add(opts.bodyClass);

	let finished = false;
	const cleanup = () => {
		if (finished) return;
		finished = true;
		window.removeEventListener("afterprint", cleanup);
		style.remove();
		if (opts.bodyClass) document.body.classList.remove(opts.bodyClass);
		opts.onAfter?.();
	};

	window.addEventListener("afterprint", cleanup);
	window.print();
}
