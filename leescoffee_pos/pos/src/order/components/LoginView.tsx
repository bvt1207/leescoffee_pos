import { useState, type FormEvent } from "react";
import { errorText, orderApi } from "../api";
import type { LoginResult, Shop } from "../types";
import BrandHeader from "./BrandHeader";

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
	const [error, setError] = useState("");

	const submit = async (e: FormEvent) => {
		e.preventDefault();
		if (busy) return;
		setError("");
		if (mobile.replace(/\D/g, "").length < 10) return setError("Vui lòng nhập số điện thoại 10 số.");
		if (name.trim().length < 2) return setError("Vui lòng nhập tên (tối thiểu 2 ký tự).");
		setBusy(true);
		try {
			onLoggedIn(await orderApi.login(qrToken, mobile, name.trim()));
		} catch (err) {
			setError(errorText(err));
		} finally {
			setBusy(false);
		}
	};

	return (
		<main className="qo-login">
			{shop.banner ? <img className="qo-login__banner" src={shop.banner} alt="" /> : null}
			<div className="qo-login__card">
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
					<label className="qo-field">
						<span className="qo-field__label">Số điện thoại</span>
						<input
							className="qo-input"
							type="tel"
							inputMode="tel"
							autoComplete="tel"
							placeholder="09xx xxx xxx"
							value={mobile}
							maxLength={15}
							onChange={(e) => setMobile(e.target.value)}
						/>
					</label>
					<label className="qo-field">
						<span className="qo-field__label">Tên của bạn</span>
						<input
							className="qo-input"
							type="text"
							autoComplete="name"
							placeholder="Tên để quán gọi khi món xong"
							value={name}
							maxLength={60}
							onChange={(e) => setName(e.target.value)}
						/>
					</label>
					{error ? (
						<div className="qo-alert qo-alert--error" role="alert">
							{error}
						</div>
					) : null}
					<button type="submit" className="qo-btn qo-btn--primary qo-btn--block" disabled={busy}>
						{busy ? "Đang vào…" : "Bắt đầu đặt món"}
					</button>
				</form>
				<p className="qo-login__fine">
					Không cần mật khẩu. Số điện thoại chỉ dùng để nhận diện đơn và tích điểm thành viên.
				</p>
			</div>
		</main>
	);
}
