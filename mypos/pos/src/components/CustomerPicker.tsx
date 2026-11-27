import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { CustomerOption } from "../types";

type Props = {
	value: CustomerOption | null;
	onChange: (customer: CustomerOption | null) => void;
};

const isDigits = (s: string) => /^[\d\s+]+$/.test(s.trim());

export default function CustomerPicker({ value, onChange }: Props) {
	const [text, setText] = useState("");
	const [options, setOptions] = useState<CustomerOption[]>([]);
	const [searched, setSearched] = useState(false);
	const [open, setOpen] = useState(false);
	const [creating, setCreating] = useState(false);
	const [newName, setNewName] = useState("");
	const [newPhone, setNewPhone] = useState("");
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState("");
	const wrapRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		const q = text.trim();
		if (!open || value || !q) {
			setOptions([]);
			setSearched(false);
			return;
		}
		const timer = setTimeout(async () => {
			try {
				setOptions(await api.searchCustomers(q));
			} catch {
				setOptions([]);
			}
			setSearched(true);
		}, 250);
		return () => clearTimeout(timer);
	}, [text, open, value]);

	useEffect(() => {
		const onDown = (e: MouseEvent) => {
			if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
		};
		document.addEventListener("mousedown", onDown);
		return () => document.removeEventListener("mousedown", onDown);
	}, []);

	const choose = (c: CustomerOption | null) => {
		onChange(c);
		setText("");
		setOptions([]);
		setOpen(false);
	};

	const openCreate = () => {
		const q = text.trim();
		if (isDigits(q)) {
			setNewPhone(q.replace(/\s/g, ""));
			setNewName("");
		} else {
			setNewName(q);
			setNewPhone("");
		}
		setError("");
		setCreating(true);
	};

	const save = async () => {
		setSaving(true);
		setError("");
		try {
			const c = await api.createCustomer(newName.trim(), newPhone.trim());
			setCreating(false);
			choose(c);
		} catch (err) {
			setError(err instanceof Error ? err.message : String(err));
		} finally {
			setSaving(false);
		}
	};

	return (
		<div className="pos-customer" ref={wrapRef}>
			{value ? (
				<div className="pos-customer__chosen">
					<div>
						<div className="pos-customer__name">{value.customer_name}</div>
						{value.mobile_no ? <div className="pos-customer__sub">{value.mobile_no}</div> : null}
					</div>
					<button type="button" className="pos-btn pos-btn--ghost" onClick={() => choose(null)}>
						Đổi
					</button>
				</div>
			) : (
				<input
					className="pos-input"
					placeholder="Số điện thoại hoặc tên (trống = khách vãng lai)"
					aria-label="Khách hàng"
					value={text}
					onFocus={() => setOpen(true)}
					onChange={(e) => {
						setText(e.target.value);
						setOpen(true);
					}}
				/>
			)}

			{open && !value && text.trim() ? (
				<div className="pos-customer__menu" role="listbox">
					{options.map((o) => (
						<button type="button" key={o.name} className="pos-customer__item" onClick={() => choose(o)}>
							<span>{o.customer_name}</span>
							<small>{o.mobile_no || "Chưa có số"}</small>
						</button>
					))}
					{searched && !options.length ? (
						<div className="pos-customer__hint">Không tìm thấy khách phù hợp</div>
					) : null}
					<button type="button" className="pos-customer__item pos-customer__item--new" onClick={openCreate}>
						+ Tạo khách mới
					</button>
				</div>
			) : null}

			{creating ? (
				<div className="pos-modal-backdrop" onClick={() => setCreating(false)}>
					<div className="pos-modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
						<div className="pos-modal__header">
							<h3>Tạo khách hàng mới</h3>
							<button type="button" className="pos-modal__close" aria-label="Đóng" onClick={() => setCreating(false)}>
								×
							</button>
						</div>
						<div className="pos-customer__form">
							<label>
								Tên khách
								<input className="pos-input" value={newName} onChange={(e) => setNewName(e.target.value)} />
							</label>
							<label>
								Số điện thoại
								<input
									className="pos-input"
									inputMode="tel"
									value={newPhone}
									onChange={(e) => setNewPhone(e.target.value)}
								/>
							</label>
							{error ? <div className="pos-alert pos-alert--error">{error}</div> : null}
							<div className="pos-customer__actions">
								<button type="button" className="pos-btn" onClick={() => setCreating(false)}>
									Hủy
								</button>
								<button
									type="button"
									className="pos-btn pos-btn--primary"
									disabled={saving || !newName.trim() || !newPhone.trim()}
									onClick={save}
								>
									{saving ? "Đang lưu…" : "Lưu khách"}
								</button>
							</div>
						</div>
					</div>
				</div>
			) : null}
		</div>
	);
}