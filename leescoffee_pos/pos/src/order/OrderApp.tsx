import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { notifyReady, unlockAudio } from "./alert";
import { errorText, OrderApiError, orderApi } from "./api";
import { attachCartStorage, cartPayload, cartStorageKey, discardCart, pruneCart, useOrderCart } from "./cart";
import BrandHeader from "./components/BrandHeader";
import CartSheet from "./components/CartSheet";
import ItemSheet from "./components/ItemSheet";
import { IconLogout, IconReceipt } from "./components/icons";
import LoginView, { shopBanners } from "./components/LoginView";
import MenuView from "./components/MenuView";
import MyOrdersPanel from "./components/MyOrdersPanel";
import OrderBanner from "./components/OrderBanner";
import OrderTypePicker from "./components/OrderTypePicker";
import PaymentView from "./components/PaymentView";
import ReadyBanner from "./components/ReadyBanner";
import { PageSkeleton } from "./components/Skeleton";
import { isActiveStage, money } from "./format";
import { usePolling } from "./poll";
import { clearSession, loadSession, readQrToken, saveSession, type StoredSession } from "./session";
import type { CustomerOrder, Me, Menu, MenuItem, OrderTypeValue, Shop } from "./types";

const POLL_MS = 5000;
const ackKey = (qr: string) => `mypos_order_ready_ack:${qr}`;

function loadAck(qr: string): string[] {
	try {
		return JSON.parse(window.localStorage.getItem(ackKey(qr)) || "[]");
	} catch {
		return [];
	}
}

function saveAck(qr: string, ids: string[]) {
	try {
		window.localStorage.setItem(ackKey(qr), JSON.stringify(ids.slice(-50)));
	} catch {
		/* ignore */
	}
}

/** Nhóm do server chia (get_my_orders.group); thiếu (server cũ) thì suy theo stage. */
const isActiveOrder = (o: CustomerOrder) => (o.group ? o.group === "active" : isActiveStage(o.stage));

export default function OrderApp() {
	const qrToken = useMemo(readQrToken, []);
	const [shop, setShop] = useState<Shop | null>(null);
	const [fatal, setFatal] = useState("");
	const [session, setSession] = useState<StoredSession | null>(() => (qrToken ? loadSession(qrToken) : null));
	const [loginNotice, setLoginNotice] = useState("");
	const [me, setMe] = useState<Me | null>(null);
	const [menus, setMenus] = useState<Menu[]>([]);
	const [currency, setCurrency] = useState("VND");
	const [menuError, setMenuError] = useState("");
	// Chỉ để hiện skeleton thay cho "Quán chưa có món" trong lúc get_menu chưa về.
	const [menuLoaded, setMenuLoaded] = useState(false);
	const [orders, setOrders] = useState<CustomerOrder[]>([]);
	const [picking, setPicking] = useState<MenuItem | null>(null);
	const [panel, setPanel] = useState<"none" | "cart" | "orders">("none");
	const [paying, setPaying] = useState<string | null>(null);
	const [ready, setReady] = useState<CustomerOrder | null>(null);
	const [toast, setToast] = useState("");
	const stages = useRef<Record<string, string>>({});
	const ordersSig = useRef("");
	// Chỉ đăng ký `lines` (+ hàm, ổn định): gõ ghi chú KHÔNG render lại cả app/menu. Ghi chú đọc lúc đặt đơn.
	const lines = useOrderCart((s) => s.lines);
	const addToCart = useOrderCart((s) => s.add);
	const clearCart = useOrderCart((s) => s.clear);

	const token = session?.token || "";
	const isOpen = (me?.shop || shop)?.is_open ?? false;

	// Lần chạm đầu tiên: mở khóa âm thanh cho tiếng báo món sẵn sàng.
	useEffect(() => {
		const once = () => unlockAudio();
		document.addEventListener("pointerdown", once, { once: true });
		return () => document.removeEventListener("pointerdown", once);
	}, []);

	useEffect(() => {
		if (!toast) return;
		const t = window.setTimeout(() => setToast(""), 3000);
		return () => window.clearTimeout(t);
	}, [toast]);

	// Thông tin quán theo mã QR (không cần đăng nhập).
	useEffect(() => {
		if (!qrToken) {
			setFatal("Đường dẫn không hợp lệ. Vui lòng quét lại mã QR tại quán.");
			return;
		}
		orderApi
			.getShop(qrToken)
			.then(setShop)
			.catch((err) => setFatal(errorText(err)));
	}, [qrToken]);

	const expireSession = useCallback(() => {
		// Phiên hết hạn (không phải Thoát): bỏ giỏ khỏi bộ nhớ nhưng GIỮ bản lưu cho lần đăng nhập lại.
		attachCartStorage(null);
		clearSession(qrToken);
		setSession(null);
		setMe(null);
		setOrders([]);
		ordersSig.current = "";
		setPaying(null);
		setPanel("none");
		setLoginNotice("Phiên đặt món đã hết hạn. Vui lòng đăng nhập lại.");
	}, [qrToken]);

	const handleError = useCallback(
		(err: unknown) => {
			if (err instanceof OrderApiError && err.sessionExpired) expireSession();
			else setToast(errorText(err));
		},
		[expireSession]
	);

	// Sau đăng nhập: thông tin khách + menu chi nhánh.
	useEffect(() => {
		if (!token) return;
		let off = false;
		setMenuLoaded(false);
		orderApi
			.getMe(token)
			.then((m) => {
				if (off) return;
				setMe(m);
				// Phiên lưu từ bản cũ chưa có cartKey -> bổ sung từ get_me.
				if (m.cart_key) {
					setSession((cur) => {
						if (!cur || cur.cartKey === m.cart_key) return cur;
						const next = { ...cur, cartKey: m.cart_key };
						saveSession(qrToken, next);
						return next;
					});
				}
			})
			.catch((err) => !off && handleError(err));
		orderApi
			.getMenu(token)
			.then((r) => {
				if (off) return;
				setMenus(r.menus);
				setCurrency(r.currency || "VND");
				setMenuError("");
				setMenuLoaded(true);
			})
			.catch((err) => {
				if (off) return;
				setMenuLoaded(true);
				if (err instanceof OrderApiError && err.sessionExpired) expireSession();
				else setMenuError(errorText(err));
			});
		return () => {
			off = true;
		};
	}, [token, qrToken, handleError, expireSession]);

	// Giỏ lưu theo (mã QR + khách). Chưa có khóa (phiên cũ, đang chờ get_me) -> chưa gắn.
	const cartKey = session?.cartKey || "";
	useEffect(() => {
		if (cartKey) attachCartStorage(cartStorageKey(qrToken, cartKey));
	}, [qrToken, cartKey]);

	// Giỏ khôi phục từ localStorage: bỏ món không còn trong menu (chạy sau khi có cả menu lẫn giỏ đã gắn;
	// giá luôn do preview tính lại).
	useEffect(() => {
		if (!cartKey || !menus.length) return;
		pruneCart(new Set(menus.flatMap((mn) => mn.items.flatMap((it) => it.sizes.map((sz) => sz.item_code)))));
	}, [menus, cartKey]);

	// Mở giỏ: tải lại trạng thái quán (mở/đóng ca) + điểm, vì có thể đã đổi từ lúc vào trang.
	useEffect(() => {
		if (panel !== "cart" || !token) return;
		orderApi
			.getMe(token)
			.then(setMe)
			.catch(handleError);
	}, [panel, token, handleError]);

	// Đơn của tôi. Gọi 1 lần khi đăng nhập / sau đặt đơn / sau thanh toán; poll 5 giây chỉ khi còn đơn
	// đang xử lý (chờ thanh toán / chưa làm / đã làm), tab đang hiện và không ở màn thanh toán
	// (PaymentView đã tự poll get_order). Phát hiện chuyển sang "Đã làm" để báo.
	const refreshOrders = useCallback(
		async (signal?: AbortSignal): Promise<CustomerOrder[] | undefined> => {
			if (!token) return undefined;
			try {
				const list = await orderApi.getMyOrders(token, signal);
				if (signal?.aborted) return undefined;
				const ack = loadAck(qrToken);
				let fresh: CustomerOrder | null = null;
				for (const o of list) {
					const before = stages.current[o.invoice_name];
					if (o.stage === "ready" && isActiveOrder(o) && before !== "ready" && !ack.includes(o.invoice_name)) fresh = o;
					stages.current[o.invoice_name] = o.stage;
				}
				// Không đổi gì -> không setState (tránh render lại menu mỗi 5 giây).
				const sig = JSON.stringify(list);
				if (sig !== ordersSig.current) {
					ordersSig.current = sig;
					setOrders(list);
				}
				if (fresh) {
					setReady(fresh);
					notifyReady();
				}
				return list;
			} catch (err) {
				if (signal?.aborted || (err instanceof OrderApiError && err.aborted)) return undefined;
				if (err instanceof OrderApiError && err.sessionExpired) {
					expireSession();
					return undefined;
				}
				throw err; // để usePolling giãn nhịp
			}
		},
		[token, qrToken, expireSession]
	);

	useEffect(() => {
		if (!token) return;
		const ctrl = new AbortController();
		refreshOrders(ctrl.signal)
			.then((list) => {
				// Vào lại (F5 / đăng nhập lại) mà còn đơn đang xử lý -> tự mở "Đơn của tôi" (nếu chưa mở gì khác).
				if (list?.some(isActiveOrder)) setPanel((p) => (p === "none" ? "orders" : p));
			})
			.catch(() => undefined);
		return () => ctrl.abort();
	}, [token, refreshOrders]);

	const hasActive = orders.some(isActiveOrder);
	usePolling(refreshOrders, !!token && !paying && hasActive, POLL_MS, { immediate: false });

	const setOrderType = (v: OrderTypeValue) => {
		if (!session) return;
		const next = { ...session, orderType: v };
		setSession(next);
		saveSession(qrToken, next);
	};

	const logout = async () => {
		// Thoát chủ động: thu hồi phiên ở server + xóa giỏ đã lưu. Đơn trên server không bị đụng.
		if (token) await orderApi.logout(token).catch(() => undefined);
		clearSession(qrToken);
		discardCart();
		setSession(null);
		setMe(null);
		setOrders([]);
		ordersSig.current = "";
		setLoginNotice("");
	};

	const checkout = async () => {
		if (!session?.orderType) throw new Error("Vui lòng chọn Mang đi hoặc Tại quán.");
		const { lines: current, note } = useOrderCart.getState();
		const created = await orderApi.createOrder(token, cartPayload(current), session.orderType, note);
		clearCart();
		setPanel("none");
		setPaying(created.invoice_name);
		refreshOrders().catch(() => undefined);
	};

	const onPaid = useCallback(
		(o: CustomerOrder) => {
			setPaying(null);
			setToast(`Đã nhận thanh toán đơn ${o.invoice_name}. Quán đang chuẩn bị món.`);
			setPanel("orders");
			refreshOrders().catch(() => undefined);
		},
		[refreshOrders]
	);

	const dismissReady = () => {
		if (ready) saveAck(qrToken, [...loadAck(qrToken), ready.invoice_name]);
		setReady(null);
	};

	// ---------- Màn hình ----------
	if (fatal) {
		return (
			<main className="qo-center">
				<div className="qo-alert qo-alert--error" role="alert">
					{fatal}
				</div>
			</main>
		);
	}
	if (!shop) {
		return <PageSkeleton />;
	}
	if (!session) {
		return (
			<LoginView
				qrToken={qrToken}
				shop={shop}
				notice={loginNotice}
				onLoggedIn={(r) => {
					const s: StoredSession = {
						token: r.session_token,
						exp: r.expires_at,
						name: r.customer_name,
						cartKey: r.cart_key,
					};
					saveSession(qrToken, s);
					stages.current = {};
					setShop(r.shop);
					setLoginNotice("");
					setSession(s);
				}}
			/>
		);
	}

	const brand = (me?.shop || shop).brand;
	const count = lines.reduce((n, l) => n + l.qty, 0);
	const subtotal = lines.reduce((n, l) => n + l.qty * l.rate, 0);
	const active = orders.filter(isActiveOrder).length;
	const loyalty = me?.loyalty || null;

	const shopNow = me?.shop || shop;
	const openOrders = () => setPanel("orders");

	return (
		<div className="qo-app">
			<header className="qo-top">
				<BrandHeader brand={brand} compact />
				<div className="qo-top__actions">
					<button
						type="button"
						className="qo-icon-btn qo-top__orders"
						onClick={openOrders}
						aria-label={`Đơn của tôi${active ? `, ${active} đơn đang xử lý` : ""}`}
						title="Đơn của tôi"
					>
						<IconReceipt />
						{active ? <span className="qo-badge-dot">{active}</span> : null}
					</button>
					<button type="button" className="qo-icon-btn" onClick={logout} aria-label="Thoát" title="Thoát">
						<IconLogout />
					</button>
				</div>
			</header>

			{!isOpen ? (
				<div className="qo-banner-closed" role="status">
					Quán chưa mở bán. Bạn có thể xem menu, nhưng chưa đặt món được.
				</div>
			) : null}

			{paying ? (
				<PaymentView
					token={token}
					invoiceName={paying}
					onPaid={onPaid}
					onBack={() => setPaying(null)}
					onSessionExpired={expireSession}
				/>
			) : !session.orderType ? (
				<main className="qo-start">
					<OrderBanner banners={shopBanners(shopNow)} />
					<OrderTypePicker
						value={session.orderType}
						onChange={setOrderType}
						greetingName={session.name}
						activeOrders={active}
						onOpenOrders={openOrders}
					/>
				</main>
			) : (
				<main className="qo-main">
					<div className="qo-strip">
						<div className="qo-strip__who">
							<span className="qo-strip__name">{session.name}</span>
							{loyalty?.enrolled ? (
								<span className="qo-strip__points">
									{loyalty.tier_name ? `${loyalty.tier_name} · ` : ""}
									{loyalty.loyalty_points ?? 0} điểm
								</span>
							) : null}
						</div>
						<OrderTypePicker variant="compact" value={session.orderType} onChange={setOrderType} />
					</div>
					{menuError ? (
						<div className="qo-alert qo-alert--error" role="alert">
							{menuError}
						</div>
					) : (
						<MenuView menus={menus} currency={currency} loading={!menuLoaded} onPick={setPicking} />
					)}
				</main>
			)}

			{/* Thanh giỏ dính đáy: chỉ khi giỏ có món và đang ở menu. "Đơn của tôi" nằm ở header (icon) + màn chọn loại đơn. */}
			{!paying && session.orderType && count ? (
				<div className="qo-dock">
					<button type="button" className="qo-dock__cart" onClick={() => setPanel("cart")}>
						<span key={count} className="qo-dock__count">
							{count}
						</span>
						<span className="qo-dock__label">Xem giỏ · {count} món</span>
						<strong className="qo-dock__total">{money(subtotal, currency)}</strong>
					</button>
				</div>
			) : null}

			{picking ? (
				<ItemSheet
					item={picking}
					currency={currency}
					onClose={() => setPicking(null)}
					onAdd={(i, opts, qty) => {
						addToCart(picking, picking.sizes[i], opts, qty);
						setPicking(null);
						setToast(`Đã thêm ${qty} ${picking.name}`);
					}}
				/>
			) : null}

			{panel === "cart" && session.orderType ? (
				<CartSheet
					token={token}
					currency={currency}
					orderType={session.orderType}
					isOpen={isOpen}
					loyalty={loyalty}
					onOrderType={setOrderType}
					onSessionExpired={expireSession}
					onCheckout={checkout}
					onClose={() => setPanel("none")}
				/>
			) : null}

			{panel === "orders" ? (
				<MyOrdersPanel
					orders={orders}
					onClose={() => setPanel("none")}
					onPay={(name) => {
						setPanel("none");
						setPaying(name);
					}}
				/>
			) : null}

			{ready ? <ReadyBanner order={ready} onDismiss={dismissReady} /> : null}
			{toast ? (
				<div className="qo-toast" role="status">
					{toast}
				</div>
			) : null}
		</div>
	);
}
