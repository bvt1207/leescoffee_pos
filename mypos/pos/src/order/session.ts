import type { OrderTypeValue } from "./types";

/**
 * Phiên khách lưu ở localStorage, tách theo mã QR (mỗi quán/mã một phiên).
 * Token do server ký (HMAC) — client chỉ giữ hộ, không tự tạo/sửa.
 */

export interface StoredSession {
	token: string;
	exp: number; // epoch giây (server)
	name: string;
	orderType?: OrderTypeValue;
	/** Khóa lưu giỏ (server cấp). Phiên cũ chưa có -> lấy từ get_me. */
	cartKey?: string;
}

const key = (qrToken: string) => `mypos_order_session:${qrToken}`;

export function readQrToken(): string {
	const m = window.location.pathname.match(/\/order\/([A-Za-z0-9_-]+)/);
	return m ? m[1] : "";
}

export function loadSession(qrToken: string): StoredSession | null {
	try {
		const raw = window.localStorage.getItem(key(qrToken));
		if (!raw) return null;
		const s = JSON.parse(raw) as StoredSession;
		if (!s.token || !s.exp || s.exp * 1000 <= Date.now()) {
			window.localStorage.removeItem(key(qrToken));
			return null;
		}
		return s;
	} catch {
		return null;
	}
}

export function saveSession(qrToken: string, s: StoredSession): void {
	try {
		window.localStorage.setItem(key(qrToken), JSON.stringify(s));
	} catch {
		/* chế độ riêng tư / hết bộ nhớ: phiên chỉ còn trong tab */
	}
}

export function clearSession(qrToken: string): void {
	try {
		window.localStorage.removeItem(key(qrToken));
	} catch {
		/* ignore */
	}
}
