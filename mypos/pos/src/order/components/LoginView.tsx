import { useState, type FormEvent } from "react";
import { errorText, orderApi } from "../api";
import type { LoginResult, Shop } from "../types";
import BrandHeader from "./BrandHeader";
import OrderBanner from "./OrderBanner";

/** Ảnh banner của quán: danh sách mới (carousel), server cũ chỉ có 1 ảnh `banner`. */
export const shopBanners = (shop: Shop) =>
	shop.banners ?? (shop.banner ? [{ title: "", image: shop.banner }] : []);

type FieldErrors = { mobile?: string; name?: string };

/** Đăng nhập bằng SĐT + tên (không mật khẩu, chưa có OTP). */
export default function LoginView({
	qrToken,
	shop,
	notice,
	onLoggedIn,
}: {
	qrToken: string;
	shop: Shop;
	notice?: string;
	onLoggedIn: (r: LoginResult) => void;
}) {
	const [mobile, setMobile] = useState("");
	const [name, setName] = useState("");
	const [busy, setBusy] = useState(false);
	const [fields, setFields] = useState<FieldErrors>({});
	const [error, setError] = useState("");

	const check = (m: string, n: string): FieldErrors => ({
		mobile: m.replace(/\D/g, "").length < 10 ? "Vui lòng nhập số điện thoại 10 số." : undefined,
		name: n.trim().length < 2 ? "Vui lòng nhập tên (tối thiểu 2 ký tự)." : undefined,
	});

	const submit = async (e: FormEvent) => {
		e.preventDefault();
		if (busy) return;
		setError("");
		const errs = check(mobile, name);
		setFields(errs);
		if (errs.mobile || errs.name) {
			document.getElementById(errs.mobile ? "qo-login-mobile" : "qo-login-name")?.focus();
			return;
		}
		setBusy(true);
		try {
			onLoggedIn(await orderApi.login(qrToken, mobile, name.trim()));
		} catch (err) {
			setError(errorText(err));
		} finally {
			setBusy(false);
		}
	};

	// Đã báo lỗi ô nào thì kiểm lại ô đó ngay khi sửa (lỗi biến mất khi nhập đúng).
	const onMobile = (v: string) => {
		setMobile(v);
		if (fields.mobile) setFields((f) => ({ ...f, mobile: check(v, name).mobile }));
	};
	const onName = (v: string) => {
		setName(v);
		if (fields.name) setFields((f) => ({ ...f, name: check(mobile, v).name }));
	};

	return (
		<main className="qo-login">
			<OrderBanner banners={shopBanners(shop)} />
			<div className="qo-login__body">
				<BrandHeader brand={shop.brand} />
				<h1 className="qo-login__title">Đặt món không cần xếp hàng</h1>
				<p className="qo-login__lead">Nhập số điện thoại để đặt món, theo dõi đơn và tích điểm.</p>
				{!shop.is_open ? (
					<div className="qo-alert qo-alert--warn" role="status">
						Quán chưa mở bán. Bạn vẫn có thể xem menu, nhưng chưa đặt món được.
					</div>
				) : null}
				{notice ? (
					<div className="qo-alert" role="status">
						{notice}
					</div>
				) : null}
				<form className="qo-form" onSubmit={submit} noValidate>
					<div className="qo-field">
						<label className="qo-field__label" htmlFor="qo-login-mobile">
							Số điện thoại
						</label>
						<input
							id="qo-login-mobile"
							className="qo-input"
							type="tel"
							inputMode="tel"
							autoComplete="tel"
							placeholder="09xx xxx xxx"
							value={mobile}
							maxLength={15}
							aria-invalid={!!fields.mobile}
							aria-describedby={fields.mobile ? "qo-login-mobile-err" : undefined}
							onChange={(e) => onMobile(e.target.value)}
						/>
						{fields.mobile ? (
							<span id="qo-login-mobile-err" className="qo-field__error">
								{fields.mobile}
							</span>
						) : null}
					</div>
					<div className="qo-field">
						<label className="qo-field__label" htmlFor="qo-login-name">
							Tên của bạn
						</label>
						<input
							id="qo-login-name"
							className="qo-input"
							type="text"
							autoComplete="name"
							placeholder="Tên để quán gọi khi món xong"
							value={name}
							maxLength={60}
							aria-invalid={!!fields.name}
							aria-describedby={fields.name ? "qo-login-name-err" : undefined}
							onChange={(e) => onName(e.target.value)}
						/>
						{fields.name ? (
							<span id="qo-login-name-err" className="qo-field__error">
								{fields.name}
							</span>
						) : null}
					</div>
					<button type="submit" className="qo-btn qo-btn--primary qo-btn--block qo-btn--lg" disabled={busy}>
						{busy ? <span className="qo-spinner qo-spinner--on-primary" aria-hidden="true" /> : null}
						{busy ? "Đang vào…" : "Bắt đầu đặt món"}
					</button>
					{error ? (
						<div className="qo-alert qo-alert--error" role="alert">
							{error}
						</div>
					) : null}
				</form>
				<p className="qo-login__fine">
					Không cần mật khẩu. Số điện thoại chỉ dùng để nhận diện đơn và tích điểm thành viên.
				</p>
			</div>
		</main>
	);
}
