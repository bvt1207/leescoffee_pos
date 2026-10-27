import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { BuzzerOption } from "../types";

type Props = {
	open: boolean;
	selected: string | null;
	onClose: () => void;
	onPick: (buzzer: BuzzerOption) => void;
};

export default function BuzzerPicker({ open, selected, onClose, onPick }: Props) {
	const [list, setList] = useState<BuzzerOption[]>([]);
	const [error, setError] = useState("");

	useEffect(() => {
		if (!open) return;
		let alive = true;
		const load = async () => {
			try {
				const data = await api.getBuzzers();
				if (alive) {
					setList(data || []);
					setError("");
				}
			} catch (err) {
				if (alive) setError(err instanceof Error ? err.message : String(err));
			}
		};
		load();
		const timer = window.setInterval(load, 5000);
		const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
		window.addEventListener("keydown", onKey);
		return () => {
			alive = false;
			window.clearInterval(timer);
			window.removeEventListener("keydown", onKey);
		};
	}, [open, onClose]);

	if (!open) return null;

	return (
		<div className="pos-modal-backdrop" onClick={onClose}>
			<div className="pos-modal pos-modal--buzzer" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
				<div className="pos-modal__header">
					<h3>Chọn thẻ rung</h3>
					<button type="button" className="pos-modal__close" aria-label="Đóng" onClick={onClose}>×</button>
				</div>
				<div className="pos-buzzer-body">
					<div className="pos-buzzer-legend">
						<span><i className="pos-dot pos-dot--ok" /> Sẵn sàng</span>
						<span><i className="pos-dot pos-dot--busy" /> Đang dùng</span>
					</div>
					{error ? <div className="pos-alert pos-alert--error">{error}</div> : null}
					{list.length ? (
						<div className="pos-buzzer-grid">
							{list.map((b) => (
								<button
									type="button"
									key={b.name}
									disabled={!b.available}
									className={`pos-buzzer ${b.available ? "is-free" : "is-busy"} ${selected === b.name ? "is-selected" : ""}`}
									onClick={() => onPick(b)}
									title={b.used_by ? `Đang giữ cho đơn ${b.used_by}` : "Sẵn sàng"}
								>
									<strong>{b.buzzer_number}</strong>
									<small>{b.available ? "Sẵn sàng" : "Đang dùng"}</small>
								</button>
							))}
						</div>
					) : (
						<div className="pos-empty">Chưa có thẻ rung nào.</div>
					)}
				</div>
			</div>
		</div>
	);
}