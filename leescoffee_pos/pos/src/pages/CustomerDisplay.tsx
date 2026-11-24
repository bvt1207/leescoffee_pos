import { useCallback, useEffect, useRef, useState } from "react";
import BannerCarousel from "../components/customer/BannerCarousel";
import { api } from "../lib/api";
import { customerLabel, shortOrderNo } from "../lib/format";
import { formatOptions } from "../lib/options";
import { useRealtimeEvent } from "../lib/realtime";
import { usePolling } from "../order/poll";
import { formatMoney } from "../store/cart";
import type { CustomerDisplayConfig, CustomerDisplayOrder, CustomerDisplayState } from "../types";

/** Giữ màn "Thanh toán thành công" bao lâu (giây) rồi về màn chờ — một nơi duy nhất. */
export const PAID_HOLD_SECONDS = 5;
/** Poll dự phòng (giây) khi socket realtime không chạy; mỗi lần chỉ đọc cache nếu không có gì mới. */
const POLL_SECONDS = 3;
/** Tải lại banner / thương hiệu (phút). */
const CONFIG_REFRESH_MINUTES = 5;
const REALTIME_EVENT = "mypos_customer_display";

/**
 * Màn hình khách (/pos/customer) — CHỈ HIỂN THỊ, không nút / input / link.
 * Đăng nhập bằng tài khoản thu ngân; server trả trạng thái của chính user đó (customer_display_api.py).
 * Mọi số tiền do server tính (preview_pricing / POS Invoice), màn này không tự tính.
 */
export default function CustomerDisplay() {
	const [config, setConfig] = useState<CustomerDisplayConfig | null>(null);
	const [state, setState] = useState<CustomerDisplayState | null>(null);
	const [error, setError] = useState<string | null>(null);
	const [paidUntil, setPaidUntil] = useState(0);
	const [, setTick] = useState(0);
	const version = useRef(0);
	const loaded = useRef(false);

	// Cấu hình (banner + thương hiệu): tải lúc mở và định kỳ.
	useEffect(() => {
		let alive = true;
		const load = () =>
			api
				.getCustomerDisplayConfig()
				.then((c) => {
					if (!alive) return;
					setConfig(c);
					if (c.brand?.name) document.title = c.brand.name;
				})
				.catch((e: Error) => alive && setError(e.message));
		void load();
		const timer = window.setInterval(load, CONFIG_REFRESH_MINUTES * 60000);
		return () => {
			alive = false;
			window.clearInterval(timer);
		};
	}, []);

	const fetchState = useCallback(async (signal?: AbortSignal) => {
		const next = await api.getCustomerDisplayState(version.current, signal);
		setError(null);
		if (next.unchanged) return;
		version.current = next.v;
		// Đơn vừa thanh toán (không phải lần tải đầu) -> giữ màn thành công PAID_HOLD_SECONDS giây.
		if (next.phase === "paid") setPaidUntil(loaded.current ? Date.now() + PAID_HOLD_SECONDS * 1000 : 0);
		loaded.current = true;
		setState(next);
	}, []);

	usePolling(
		(signal) =>
			fetchState(signal).catch((e: Error) => {
				if (!signal.aborted) setError(e.message);
				throw e;
			}),
		true,
		POLL_SECONDS * 1000
	);

	// Realtime: server báo phiên bản mới -> lấy ngay (poll vẫn chạy làm dự phòng).
	useRealtimeEvent(REALTIME_EVENT, () => {
		void fetchState().catch(() => undefined);
	});

	// Hết thời gian giữ màn thành công -> vẽ lại để về màn chờ.
	useEffect(() => {
		if (!paidUntil) return;
		const wait = paidUntil - Date.now();
		if (wait <= 0) return;
		const timer = window.setTimeout(() => setTick((t) => t + 1), wait + 50);
		return () => window.clearTimeout(timer);
	}, [paidUntil]);

	// Bật toàn màn hình ở lần chạm đầu (trình duyệt yêu cầu thao tác người dùng; không được thì bỏ qua).
	const requestFullscreen = () => {
		const el = document.documentElement;
		if (!document.fullscreenElement && el.requestFullscreen) void el.requestFullscreen().catch(() => undefined);
	};

	const brand = config?.brand || {};
	const banners = config?.banners || [];
	const currency = state?.order?.currency || config?.currency || "VND";

	let phase = state?.phase || "idle";
	if (phase === "paid" && Date.now() >= paidUntil) phase = "idle";

	let body;
	if (!config && error) {
		body = <div className="pos-cd-message">{error}</div>;
	} else if (phase === "idle" || !state?.order) {
		body = <BannerCarousel banners={banners} brandName={brand.name} brandLogo={brand.logo} variant="full" />;
	} else if (phase === "qr" && state.qr) {
		body = <QrView order={state.order} qr={state.qr} currency={currency} brandName={brand.name} brandLogo={brand.logo} />;
	} else {
		body = (
			<div className="pos-cd-split">
				<BannerCarousel banners={banners} brandName={brand.name} brandLogo={brand.logo} variant="side" />
				<OrderPanel order={state.order} currency={currency} paid={phase === "paid"} />
			</div>
		);
	}

	return (
		<div className="pos-cd" onPointerDown={requestFullscreen}>
			{body}
			{error && config ? <div className="pos-cd-offline">Mất kết nối, đang thử lại…</div> : null}
		</div>
	);
}

function customerText(order: CustomerDisplayOrder): string {
	return customerLabel({ customer_name: order.customer.name, is_walk_in: order.customer.is_walk_in });
}

function OrderPanel({ order, currency, paid }: { order: CustomerDisplayOrder; currency: string; paid: boolean }) {
	const t = order.totals;
	const listRef = useRef<HTMLDivElement>(null);
	const lineCount = order.lines.length;

	// Món mới thêm nằm cuối danh sách -> cuộn tới cuối để khách thấy.
	useEffect(() => {
		const el = listRef.current;
		if (el) el.scrollTop = el.scrollHeight;
	}, [lineCount]);

	const subtotal = t.total_before + t.total_surcharge;
	return (
		<section className="pos-cd-panel">
			<header className="pos-cd-panel__head">
				<div className="pos-cd-panel__title">{order.invoice ? `Đơn ${shortOrderNo(order.invoice)}` : "Món đã chọn"}</div>
				<div className="pos-cd-customer">
					<span className="pos-cd-customer__name">{customerText(order)}</span>
					{order.customer.tier_name ? <span className="pos-cd-customer__tier">{order.customer.tier_name}</span> : null}
					{order.customer.loyalty_points != null ? (
						<span className="pos-cd-customer__points">{order.customer.loyalty_points.toLocaleString("vi-VN")} điểm</span>
					) : null}
				</div>
			</header>

			<div className="pos-cd-lines" ref={listRef}>
				{order.lines.map((line, i) => {
					const opts = formatOptions(line.options, true);
					return (
						<div className="pos-cd-line" key={`${line.item_name}-${i}`}>
							<div className="pos-cd-line__qty">{line.qty}×</div>
							<div className="pos-cd-line__info">
								<div className="pos-cd-line__name">
									{line.item_name}
									{line.size ? <span className="pos-cd-line__size">{line.size}</span> : null}
								</div>
								{opts ? <div className="pos-cd-line__opts">{opts}</div> : null}
								{line.is_free_item ? <div className="pos-cd-line__gift">Quà tặng</div> : null}
							</div>
							<div className="pos-cd-line__amount">
								{line.is_free_item ? formatMoney(0, currency) : formatMoney(line.amount, currency)}
								{!line.is_free_item && line.rate < line.price_list_rate ? (
									<div className="pos-cd-line__was">{formatMoney(line.price_list_rate * line.qty, currency)}</div>
								) : null}
							</div>
						</div>
					);
				})}
			</div>

			<div className="pos-cd-totals">
				<Row label="Tạm tính" value={formatMoney(subtotal, currency)} />
				{t.total_discount_rules > 0 ? (
					<Row label="Khuyến mãi" value={`−${formatMoney(t.total_discount_rules, currency)}`} tone="saving" />
				) : null}
				{t.loyalty_discount > 0 ? (
					<Row
						label={t.redeemed_points ? `Đổi ${t.redeemed_points.toLocaleString("vi-VN")} điểm` : "Đổi điểm"}
						value={`−${formatMoney(t.loyalty_discount, currency)}`}
						tone="saving"
					/>
				) : null}
				{t.total_surcharge > 0 ? (
					<div className="pos-cd-totals__note">Gồm phụ thu topping {formatMoney(t.total_surcharge, currency)}</div>
				) : null}
				<Row label="Tổng cộng" value={formatMoney(t.amount_total, currency)} strong />
				<div className={`pos-cd-due${paid ? " is-paid" : ""}`}>
					<div className="pos-cd-due__label">Số tiền phải thu</div>
					<div className="pos-cd-due__value">{formatMoney(paid ? 0 : t.amount_due, currency)}</div>
				</div>
				{paid ? (
					<div className="pos-cd-paid" role="status">
						<span className="pos-cd-paid__icon" aria-hidden="true">✓</span>
						Thanh toán thành công. Cảm ơn quý khách!
					</div>
				) : null}
			</div>
		</section>
	);
}

function Row({ label, value, tone, strong }: { label: string; value: string; tone?: "saving"; strong?: boolean }) {
	return (
		<div className={`pos-cd-row${tone ? ` pos-cd-row--${tone}` : ""}${strong ? " pos-cd-row--strong" : ""}`}>
			<span>{label}</span>
			<span>{value}</span>
		</div>
	);
}

function QrView({
	order,
	qr,
	currency,
	brandName,
	brandLogo,
}: {
	order: CustomerDisplayOrder;
	qr: { qr_url: string; amount: number; payment_code: string };
	currency: string;
	brandName?: string;
	brandLogo?: string;
}) {
	return (
		<div className="pos-cd-qr">
			<div className="pos-cd-qr__brand">
				{brandLogo ? <img src={brandLogo} alt="" /> : null}
				{brandName ? <span>{brandName}</span> : null}
			</div>
			<div className="pos-cd-qr__card">
				<img className="pos-cd-qr__img" src={qr.qr_url} alt="Mã QR thanh toán" />
				<div className="pos-cd-qr__info">
					<div className="pos-cd-qr__hint">Quét mã bằng ứng dụng ngân hàng để thanh toán</div>
					<div className="pos-cd-qr__label">Số tiền phải thu</div>
					<div className="pos-cd-qr__amount">{formatMoney(qr.amount || order.totals.amount_due, currency)}</div>
					<div className="pos-cd-qr__meta">
						{order.invoice ? <span>Đơn {shortOrderNo(order.invoice)}</span> : null}
						<span>{customerText(order)}</span>
					</div>
					{qr.payment_code ? (
						<div className="pos-cd-qr__code">
							Nội dung chuyển khoản
							<strong>{qr.payment_code}</strong>
						</div>
					) : null}
				</div>
			</div>
		</div>
	);
}
