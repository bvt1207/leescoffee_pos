/**
 * Định dạng thời gian + mã đơn dùng chung cho màn nhân viên (Orders, hóa đơn in).
 *
 * Chuỗi thời gian server ("2026-11-20 11:38:05.123") là giờ của site, không có múi giờ:
 * chỉ cắt chuỗi, không đổi múi. "Hôm nay"/"Hôm qua" so với ngày hiện tại theo SITE_TZ
 * (để máy quầy đặt sai múi giờ vẫn ra đúng ngày).
 */
export const SITE_TZ = "Asia/Ho_Chi_Minh";

const STAMP_RE = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/;

type Parts = { y: string; m: string; d: string; hh: string; mm: string };

function parse(value: string): Parts | null {
	const match = STAMP_RE.exec(String(value || ""));
	if (!match) return null;
	const [, y, m, d, hh, mm] = match;
	return { y, m, d, hh, mm };
}

/** Thời điểm hiện tại theo múi giờ của site. */
function nowParts(timeZone = SITE_TZ): Parts {
	const parts = new Intl.DateTimeFormat("en-GB", {
		timeZone,
		year: "numeric",
		month: "2-digit",
		day: "2-digit",
		hour: "2-digit",
		minute: "2-digit",
		hourCycle: "h23",
	}).formatToParts(new Date());
	const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
	return { y: get("year"), m: get("month"), d: get("day"), hh: get("hour"), mm: get("minute") };
}

const isoDay = (p: Parts) => `${p.y}-${p.m}-${p.d}`;

/** Cộng/trừ ngày trên chuỗi "YYYY-MM-DD" (tính trên lịch, không phụ thuộc múi giờ máy). */
export function addDaysIso(day: string, days: number): string {
	const [y, m, d] = day.split("-").map(Number);
	return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
}

/** Hôm nay ("YYYY-MM-DD") theo múi giờ site. */
export function todayIso(timeZone = SITE_TZ): string {
	return isoDay(nowParts(timeZone));
}

/** "Hôm nay 11:38" · "Hôm qua 20:15" · "17/11 20:15" · khác năm "17/11/2025 20:15". */
export function formatOrderTime(value: string, timeZone = SITE_TZ): string {
	const p = parse(value);
	if (!p) return String(value || "");
	const time = `${p.hh}:${p.mm}`;
	const now = nowParts(timeZone);
	const day = isoDay(p);
	if (day === isoDay(now)) return `Hôm nay ${time}`;
	if (day === addDaysIso(isoDay(now), -1)) return `Hôm qua ${time}`;
	return p.y === now.y ? `${p.d}/${p.m} ${time}` : `${p.d}/${p.m}/${p.y} ${time}`;
}

/** Ngày giờ tuyệt đối "20/11/2026 11:38" — dùng cho bản in (giấy in không ghi "Hôm nay"). */
export function formatStamp(value: string): string {
	const p = parse(value);
	return p ? `${p.d}/${p.m}/${p.y} ${p.hh}:${p.mm}` : String(value || "");
}

/** Giờ in hiện tại theo múi giờ site, cùng định dạng với `formatStamp`. */
export function nowStamp(timeZone = SITE_TZ): string {
	const p = nowParts(timeZone);
	return `${p.d}/${p.m}/${p.y} ${p.hh}:${p.mm}`;
}

/** "ACC-PSINV-2026-00016" → "#00016" (cụm số cuối). Không có cụm số → giữ nguyên mã. */
export function shortOrderNo(name: string): string {
	const match = /(\d+)$/.exec(String(name || ""));
	return match ? `#${match[1]}` : String(name || "");
}

/** Tìm đơn theo mã đầy đủ, mã ngắn ("#00016", "00016", "16") hoặc tên khách. `query` đã trim + lowercase. */
export function orderMatches(order: { name: string; customer_name?: string | null }, query: string): boolean {
	const q = query.replace(/^#/, "");
	if (!q) return true;
	return (
		order.name.toLowerCase().includes(q) ||
		shortOrderNo(order.name).toLowerCase().includes(q) ||
		(order.customer_name || "").toLowerCase().includes(q)
	);
}
