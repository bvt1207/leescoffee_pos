import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import StatusColumn, { type BoardEntry } from "../components/status/StatusColumn";
import { api } from "../lib/api";
import { CHANGE_POLL_MS, REALTIME_EVENT, REALTIME_POLL_MS } from "../lib/changes";
import { useRealtimeEvent } from "../lib/realtime";
import { usePolling } from "../order/poll";
import type { OrderStatusBoard, OrderStatusConfig } from "../types";
import "../styles/status-board.css";

/**
 * Màn theo dõi đơn cho khách nhìn (/pos/status, treo TV) — CHỈ ĐỌC: không nút, không âm thanh, không link.
 * Dữ liệu: order_status_api.py (server đã rút gọn tên, không có SĐT / tiền / món). `docs/rules/order_status.md`.
 *
 * Cập nhật dùng chung cơ chế phiên bản thay đổi theo POS Profile (realtime.md): nghe `mypos_pos_changed` {p, v},
 * poll phiên bản CHANGE_POLL_MS (4 giây) khi không có socket / REALTIME_POLL_MS (30 giây) khi có; chỉ tải danh sách khi
 * phiên bản đổi + lưới an toàn STATUS_SAFETY_REFRESH_MS.
 */

/** Lưới an toàn: tải lại danh sách dù phiên bản không đổi — bắt thay đổi không qua hook (vd. đóng ca gộp đơn bằng SQL). */
export const STATUS_SAFETY_REFRESH_MS = 60000;
/** Tải lại thương hiệu / danh sách profile. */
const CONFIG_REFRESH_MS = 5 * 60000;
/** Ẩn con trỏ chuột sau chừng này ms không di chuyển. */
const CURSOR_HIDE_MS = 3000;
/** Lỗi liên tục quá mốc này -> chấm trạng thái đỏ (dưới mốc: vàng). */
const STALE_AFTER_MS = 30000;
/** Thời gian dịch chuyển của dòng (≤ 300ms). */
const MOVE_MS = 280;
/** Quản lý chọn POS Profile: ghi nhớ ở trình duyệt. */
const PROFILE_STORAGE_KEY = "mypos_status_profile";

function readStoredProfile(): string {
	try {
		return window.localStorage.getItem(PROFILE_STORAGE_KEY) || "";
	} catch {
		return "";
	}
}

function storeProfile(name: string) {
	try {
		window.localStorage.setItem(PROFILE_STORAGE_KEY, name);
	} catch {
		/* trình duyệt chặn localStorage: chỉ nhớ trong phiên */
	}
}

/** Gắn khóa ổn định cho từng dòng (mã ngắn; trùng mã ở 2 loạt hóa đơn -> thêm hậu tố). */
function withKeys(board: OrderStatusBoard | null) {
	const seen = new Map<string, number>();
	const tag = (e: OrderStatusBoard["preparing"][number]): BoardEntry => {
		const n = (seen.get(e.code) || 0) + 1;
		seen.set(e.code, n);
		return { ...e, key: n > 1 ? `${e.code}~${n}` : e.code };
	};
	return {
		preparing: board ? board.preparing.map(tag) : [],
		ready: board ? board.ready.map(tag) : [],
	};
}

const clockText = () =>
	new Intl.DateTimeFormat("vi-VN", { hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date());

export default function OrderStatus() {
	const [choice, setChoice] = useState(readStoredProfile);
	const [config, setConfig] = useState<OrderStatusConfig | null>(null);
	const [fatal, setFatal] = useState("");
	const [board, setBoard] = useState<OrderStatusBoard | null>(null);
	const [connected, setConnected] = useState(false);
	const [failingSince, setFailingSince] = useState<number | null>(null);
	const [clock, setClock] = useState(clockText);
	const [idle, setIdle] = useState(false);
	const seenV = useRef<string | null>(null);
	const loading = useRef({ running: false, again: false });
	const rootRef = useRef<HTMLDivElement>(null);
	const rects = useRef(new Map<string, DOMRect>());

	const profile = config?.profile || "";
	// Gửi lựa chọn của quản lý; server bỏ qua với Cashier / Kitchen.
	const sent = choice || undefined;

	const ok = useCallback(() => setFailingSince(null), []);
	const fail = useCallback(() => setFailingSince((t) => t ?? Date.now()), []);

	// Cấu hình: lúc mở, khi đổi profile, và định kỳ. Lỗi lần đầu (chưa thuộc POS Profile...) -> hiện thông báo.
	useEffect(() => {
		let alive = true;
		const load = () =>
			api
				.getOrderStatusConfig(sent)
				.then((c) => {
					if (!alive) return;
					// Profile đã nhớ không còn trong danh sách được chọn -> bỏ.
					if (choice && c.profiles.length && !c.profiles.includes(choice)) {
						storeProfile("");
						setChoice("");
					}
					setConfig(c);
					setFatal("");
				})
				.catch((err: Error) => {
					if (!alive) return;
					// Profile đã nhớ bị xóa / tắt -> bỏ lựa chọn, tải lại theo profile mặc định.
					if (choice) {
						storeProfile("");
						setChoice("");
						return;
					}
					setConfig((cur) => {
						if (!cur) setFatal(err.message);
						return cur;
					});
				});
		void load();
		const t = window.setInterval(load, CONFIG_REFRESH_MS);
		return () => {
			alive = false;
			window.clearInterval(t);
		};
	}, [sent, choice]);

	// Tải danh sách; không chồng request (đang chạy mà có yêu cầu mới -> chạy thêm đúng một lần).
	const loadBoard = useCallback(async () => {
		const st = loading.current;
		if (st.running) {
			st.again = true;
			return;
		}
		st.running = true;
		try {
			do {
				st.again = false;
				try {
					const b = await api.getOrderStatusBoard(sent);
					seenV.current = b.v;
					setBoard(b);
					ok();
				} catch {
					fail(); // giữ danh sách cuối cùng
				}
			} while (st.again);
		} finally {
			st.running = false;
		}
	}, [sent, ok, fail]);

	const ready = !!config;

	// Mở màn / đổi profile -> tải ngay.
	useEffect(() => {
		if (!ready) return;
		seenV.current = null;
		void loadBoard();
	}, [ready, profile, loadBoard]);

	// Poll phiên bản (chỉ đọc Redis). Tab ẩn -> dừng; hiện lại -> hỏi ngay (usePolling).
	usePolling(
		async (signal) => {
			try {
				const r = await api.getOrderStatusChanges(sent, signal);
				ok();
				if (r.v !== seenV.current) await loadBoard();
			} catch (err) {
				if (!signal.aborted) fail();
				throw err;
			}
		},
		ready,
		connected ? REALTIME_POLL_MS : CHANGE_POLL_MS,
		{ immediate: false }
	);

	// Realtime: {p, v} của mọi profile (phòng "all") -> chỉ nhận đúng profile đang hiện. data = null: vừa kết nối lại.
	useRealtimeEvent(
		REALTIME_EVENT,
		(data) => {
			const msg = data as { p?: string; v?: string } | null;
			if (!msg) {
				void loadBoard();
				return;
			}
			if (msg.p === profile && msg.v != null && String(msg.v) !== seenV.current) void loadBoard();
		},
		ready,
		setConnected
	);

	// Lưới an toàn + tab hiện lại / máy ngủ dậy -> làm mới một lần.
	useEffect(() => {
		if (!ready) return;
		const t = window.setInterval(() => {
			if (document.visibilityState === "visible") void loadBoard();
		}, STATUS_SAFETY_REFRESH_MS);
		const onVisible = () => document.visibilityState === "visible" && void loadBoard();
		document.addEventListener("visibilitychange", onVisible);
		window.addEventListener("online", onVisible);
		return () => {
			window.clearInterval(t);
			document.removeEventListener("visibilitychange", onVisible);
			window.removeEventListener("online", onVisible);
		};
	}, [ready, loadBoard]);

	// Đồng hồ (HH:MM) + làm mới mốc lỗi để chấm trạng thái đổi màu đúng lúc.
	const [, setTick] = useState(0);
	useEffect(() => {
		const t = window.setInterval(() => {
			setClock(clockText());
			setTick((n) => n + 1);
		}, 15000);
		return () => window.clearInterval(t);
	}, []);

	// Ẩn con trỏ khi không di chuột.
	useEffect(() => {
		let t = window.setTimeout(() => setIdle(true), CURSOR_HIDE_MS);
		const onMove = () => {
			setIdle(false);
			window.clearTimeout(t);
			t = window.setTimeout(() => setIdle(true), CURSOR_HIDE_MS);
		};
		window.addEventListener("mousemove", onMove);
		return () => {
			window.clearTimeout(t);
			window.removeEventListener("mousemove", onMove);
		};
	}, []);

	const entries = useMemo(() => withKeys(board), [board]);
	const boardKeys = useMemo(
		() => new Set([...entries.preparing, ...entries.ready].map((e) => e.key)),
		[entries]
	);

	// Dịch chuyển mượt (FLIP): dòng đổi chỗ / sang cột kia trượt tới vị trí mới, dòng mới hiện dần.
	useLayoutEffect(() => {
		const root = rootRef.current;
		if (!root) return;
		const motion = !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
		const first = rects.current.size === 0;
		const next = new Map<string, DOMRect>();
		root.querySelectorAll<HTMLElement>("[data-sb-key]").forEach((el) => {
			const key = el.dataset.sbKey as string;
			const rect = el.getBoundingClientRect();
			next.set(key, rect);
			if (!motion || first || typeof el.animate !== "function") return;
			const old = rects.current.get(key);
			if (old) {
				const dx = old.left - rect.left;
				const dy = old.top - rect.top;
				if (Math.abs(dx) > 1 || Math.abs(dy) > 1) {
					el.animate([{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "none" }], {
						duration: MOVE_MS,
						easing: "cubic-bezier(0.2, 0.7, 0.2, 1)",
					});
				}
			} else {
				el.animate([{ opacity: 0, transform: "translateY(12px)" }, { opacity: 1, transform: "none" }], {
					duration: MOVE_MS,
					easing: "ease-out",
				});
			}
		});
		rects.current = next;
	}, [entries]);

	// Đổi kích thước cửa sổ: vị trí cũ không còn đúng -> bỏ, lần cập nhật sau không trượt từ chỗ sai.
	useEffect(() => {
		const reset = () => {
			rects.current = new Map();
		};
		window.addEventListener("resize", reset);
		return () => window.removeEventListener("resize", reset);
	}, []);

	if (fatal) {
		return (
			<div className="pos-sb pos-sb--message">
				<p className="pos-sb__message">{fatal}</p>
			</div>
		);
	}

	const stale = failingSince !== null && Date.now() - failingSince >= STALE_AFTER_MS;
	const health = stale ? "bad" : failingSince !== null || !connected ? "warn" : "ok";
	const healthText =
		health === "ok" ? "Đang cập nhật trực tiếp" : health === "warn" ? "Cập nhật định kỳ" : "Mất kết nối, đang thử lại";
	const brand = config?.brand;
	const brandName = brand?.name || "";

	return (
		<div ref={rootRef} className={`pos-sb${idle ? " pos-sb--idle" : ""}`}>
			<header className="pos-sb__top">
				<div className="pos-sb__brand">
					{brand?.logo ? <img className="pos-sb__logo" src={brand.logo} alt="" /> : null}
					{brandName ? <span className="pos-sb__name">{brandName}</span> : null}
				</div>
				<div className="pos-sb__right">
					{config && config.profiles.length > 1 ? (
						<select
							className="pos-sb__profile"
							aria-label="POS Profile"
							value={choice || config.profile}
							onChange={(e) => {
								storeProfile(e.target.value);
								setChoice(e.target.value);
							}}
						>
							{config.profiles.map((p) => (
								<option key={p} value={p}>
									{p}
								</option>
							))}
						</select>
					) : null}
					<time className="pos-sb__clock">{clock}</time>
					<span className={`pos-sb__health pos-sb__health--${health}`} title={healthText} aria-label={healthText} />
				</div>
			</header>

			<main className="pos-sb__cols">
				{board ? (
					<>
						<StatusColumn
							variant="preparing"
							title="Đang chuẩn bị"
							emptyText="Chưa có đơn đang chuẩn bị"
							items={entries.preparing}
							more={board.more.preparing}
							boardKeys={boardKeys}
						/>
						<StatusColumn
							variant="ready"
							title="Sẵn sàng nhận món"
							emptyText="Chưa có đơn sẵn sàng"
							items={entries.ready}
							more={board.more.ready}
							boardKeys={boardKeys}
						/>
					</>
				) : (
					<>
						<section className="pos-sb-col pos-sb-col--preparing pos-sb-col--loading" aria-busy="true" />
						<section className="pos-sb-col pos-sb-col--ready pos-sb-col--loading" aria-busy="true" />
					</>
				)}
			</main>
		</div>
	);
}
