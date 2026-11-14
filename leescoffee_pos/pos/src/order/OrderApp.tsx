import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { notifyReady, unlockAudio } from "./alert";
import { errorText, OrderApiError, orderApi } from "./api";
import { cartPayload, useOrderCart } from "./cart";
import BrandHeader from "./components/BrandHeader";
import CartSheet from "./components/CartSheet";
import ItemSheet from "./components/ItemSheet";
import LoginView from "./components/LoginView";
import MenuView from "./components/MenuView";
import MyOrdersPanel from "./components/MyOrdersPanel";
import OrderTypePicker from "./components/OrderTypePicker";
import PaymentView from "./components/PaymentView";
import ReadyBanner from "./components/ReadyBanner";
import { isActiveStage, money, orderTypeLabel } from "./format";
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
	const [orders, setOrders] = useState<CustomerOrder[]>([]);
	const [picking, setPicking] = useState<MenuItem | null>(null);
	const [panel, setPanel] = useState<"none" | "cart" | "orders">("none");
	const [paying, setPaying] = useState<string | null>(null);
	const [ready, setReady] = useState<CustomerOrder | null>(null);
	const [toast, setToast] = useState("");
	const stages = useRef<Record<string, string>>({});
	const cart = useOrderCart();

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
		clearSession(qrToken);
		setSession(null);
		setMe(null);
		setOrders([]);
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
		orderApi
			.getMe(token)
			.then((m) => !off && setMe(m))
			.catch((err) => !off && handleError(err));
		orderApi
			.getMenu(token)
			.then((r) => {
				if (off) return;
				setMenus(r.menus);
				setCurrency(r.currency || "VND");
				setMenuError("");
			})
			.catch((err) => {
				if (off) return;
				if (err instanceof OrderApiError && err.sessionExpired) expireSession();
				else setMenuError(errorText(err));
			});
		return () => {
			off = true;
		};
	}, [token, handleError, expireSession]);

	// Mở giỏ: tải lại trạng thái quán (mở/đóng ca) + điểm, vì có thể đã đổi từ lúc vào trang.
	useEffect(() => {
		if (panel !== "cart" || !token) return;
		orderApi
			.getMe(token)
			.then(setMe)
			.catch(handleError);
	}, [panel, token, handleError]);

	// Đơn của tôi: làm mới 5 giây khi tab đang mở; phát hiện chuyển sang "Đã làm" để báo.
	const refreshOrders = useCallback(async () => {
		if (!token) return;
		try {
			const list = await orderApi.getMyOrders(token);
			const ack = loadAck(qrToken);
			let fresh: CustomerOrder | null = null;
			for (const o of list) {
				const before = stages.current[o.invoice_name];
				if (o.stage === "ready" && before !== "ready" && !ack.includes(o.invoice_name)) fresh = o;
				stages.current[o.invoice_name] = o.stage;
			}
			setOrders(list);
			if (fresh) {
				setReady(fresh);
				notifyReady();
			}
		} catch (err) {
			if (err instanceof OrderApiError && err.sessionExpired) expireSession();
		}
	}, [token, qrToken, expireSession]);

	useEffect(() => {
		if (!token) return;
		void refreshOrders();
		const t = window.setInterval(() => {
			if (document.visibilityState === "visible") void refreshOrders();
		}, POLL_MS);
		const onVisible = () => document.visibilityState === "visible" && void refreshOrders();
		document.addEventListener("visibilitychange", onVisible);
		return () => {
			window.clearInterval(t);
			document.removeEventListener("visibilitychange", onVisible);
		};
	}, [token, refreshOrders]);

	const setOrderType = (v: OrderTypeValue) => {
		if (!session) return;
		const next = { ...session, orderType: v };
		setSession(next);
		saveSession(qrToken, next);
	};

	const logout = async () => {
		if (token) await orderApi.logout(token).catch(() => undefined);
		clearSession(qrToken);
		cart.clear();
		setSession(null);
		setMe(null);
		setOrders([]);
		setLoginNotice("");
	};

	const checkout = async () => {
		if (!session?.orderType) throw new Error("Vui lòng chọn Mang đi hoặc Tại quán.");
		const created = await orderApi.createOrder(token, cartPayload(cart.lines), session.orderType, cart.note);
		cart.clear();
		setPanel("none");
		setPaying(created.invoice_name);
		void refreshOrders();
	};

	const onPaid = useCallback(
		(o: CustomerOrder) => {
			setPaying(null);
			setToast(`Đã nhận thanh toán đơn ${o.invoice_name}. Quán đang chuẩn bị món.`);
			setPanel("orders");
			void refreshOrders();
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
		return (
			<main className="qo-center">
				<span className="qo-spinner" aria-label="Đang tải" />
			</main>
		);
	}
	if (!session) {
		return (
			<LoginView
				qrToken={qrToken}
				shop={shop}
				notice={loginNotice}
				onLoggedIn={(r) => {
					const s: StoredSession = { token: r.session_token, exp: r.expires_at, name: r.customer_name };
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
	const count = cart.lines.reduce((n, l) => n + l.qty, 0);
	const subtotal = cart.lines.reduce((n, l) => n + l.qty * l.rate, 0);
	const active = orders.filter((o) => isActiveStage(o.stage)).length;
	const loyalty = me?.loyalty || null;

	return (
		<div className="qo-app">
			<header className="qo-top">
				<BrandHeader brand={brand} compact />
				<div className="qo-top__user">
					<span className="qo-top__name">{session.name}</span>
					{loyalty?.enrolled ? (
						<span className="qo-top__points">
							{loyalty.tier_name ? `${loyalty.tier_name} · ` : ""}
							{loyalty.loyalty_points ?? 0} điểm
						</span>
					) : null}
					<button type="button" className="qo-link" onClick={logout}>
						Thoát
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
				<OrderTypePicker value={session.orderType} onChange={setOrderType} />
			) : (
				<main className="qo-main">
					<div className="qo-main__type">
						<span>
							Đang đặt: <strong>{orderTypeLabel(session.orderType)}</strong>
						</span>
						<OrderTypePicker variant="segmented" value={session.orderType} onChange={setOrderType} />
					</div>
					{menuError ? (
						<div className="qo-alert qo-alert--error" role="alert">
							{menuError}
						</div>
					) : (
						<MenuView menus={menus} currency={currency} onPick={setPicking} />
					)}
				</main>
			)}

			{!paying ? (
				<div className="qo-dock">
					<button
						type="button"
						className="qo-dock__orders"
						onClick={() => setPanel("orders")}
						aria-label={`Đơn của tôi${active ? `, ${active} đơn đang xử lý` : ""}`}
					>
						Đơn của tôi
						{active ? <span className="qo-dock__badge">{active}</span> : null}
					</button>
					{count ? (
						<button type="button" className="qo-dock__cart" onClick={() => setPanel("cart")}>
							<span className="qo-dock__count">{count}</span>
							<span>Xem giỏ</span>
							<strong>{money(subtotal, currency)}</strong>
						</button>
					) : null}
				</div>
			) : null}

			{picking ? (
				<ItemSheet
					item={picking}
					currency={currency}
					onClose={() => setPicking(null)}
					onAdd={(i, opts, qty) => {
						cart.add(picking, picking.sizes[i], opts, qty);
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
