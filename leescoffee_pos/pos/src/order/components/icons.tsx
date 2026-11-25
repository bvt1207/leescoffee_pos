import type { ReactNode, SVGProps } from "react";

/** Bộ icon nét (stroke) đồng nhất cho web đặt món: 24×24, nét 1.75, đầu tròn. Màu theo currentColor.
 *  Vẽ tay bằng SVG inline (không thêm thư viện icon). Mọi icon mặc định aria-hidden: nghĩa nằm ở chữ / aria-label của nút. */
type Props = SVGProps<SVGSVGElement> & { size?: number };

function make(paths: ReactNode) {
	return function Icon({ size = 22, ...rest }: Props) {
		return (
			<svg
				width={size}
				height={size}
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				strokeWidth={1.75}
				strokeLinecap="round"
				strokeLinejoin="round"
				aria-hidden="true"
				focusable="false"
				{...rest}
			>
				{paths}
			</svg>
		);
	};
}

/** Túi giấy — Mang đi. */
export const IconBag = make(
	<>
		<path d="M5 8h14l-1 12.2a1 1 0 0 1-1 .8H7a1 1 0 0 1-1-.8L5 8Z" />
		<path d="M9 10V6a3 3 0 0 1 6 0v4" />
	</>
);

/** Tách có quai + đĩa — Tại quán. */
export const IconCup = make(
	<>
		<path d="M4 9h12v4a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5V9Z" />
		<path d="M16 10h1.5a2.5 2.5 0 0 1 0 5H16" />
		<path d="M3 21h15" />
		<path d="M8 3c-.6.8-.6 1.7 0 2.5M12 3c-.6.8-.6 1.7 0 2.5" />
	</>
);

/** Biên nhận — Đơn của tôi. */
export const IconReceipt = make(
	<>
		<path d="M6 3h12v18l-2-1.4-2 1.4-2-1.4-2 1.4-2-1.4L6 21V3Z" />
		<path d="M9.5 8h5M9.5 12h5" />
	</>
);

export const IconSearch = make(
	<>
		<circle cx="11" cy="11" r="6.5" />
		<path d="m20 20-4.2-4.2" />
	</>
);

export const IconPlus = make(<path d="M12 5v14M5 12h14" />);

export const IconMinus = make(<path d="M5 12h14" />);

export const IconClose = make(<path d="M6 6l12 12M18 6 6 18" />);

export const IconCheck = make(<path d="m5 12.5 4.5 4.5L19 7.5" />);

export const IconCopy = make(
	<>
		<rect x="8.5" y="8.5" width="11" height="11" rx="2" />
		<path d="M15.5 8.5V6a1.5 1.5 0 0 0-1.5-1.5H6A1.5 1.5 0 0 0 4.5 6v8A1.5 1.5 0 0 0 6 15.5h2.5" />
	</>
);

export const IconLogout = make(
	<>
		<path d="M14 4h4a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-4" />
		<path d="M10 16l-4-4 4-4M6 12h9" />
	</>
);

export const IconChevronRight = make(<path d="m9.5 6 6 6-6 6" />);

export const IconPin = make(
	<>
		<path d="M12 21s6.5-5.6 6.5-11a6.5 6.5 0 0 0-13 0c0 5.4 6.5 11 6.5 11Z" />
		<circle cx="12" cy="10" r="2.3" />
	</>
);

export const IconStore = make(
	<>
		<path d="M4 9.5 5.5 4h13L20 9.5" />
		<path d="M4 9.5a2.7 2.7 0 0 0 5.3 0 2.7 2.7 0 0 0 5.4 0 2.7 2.7 0 0 0 5.3 0" />
		<path d="M5.5 12v8h13v-8" />
		<path d="M10 20v-4.5h4V20" />
	</>
);
