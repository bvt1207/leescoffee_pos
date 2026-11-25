import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { usePosRefresh } from "../lib/changes";
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

	// Thẻ "Đang dùng" tính theo đơn còn giữ -> tải khi mở modal, khi phiên bản thay đổi của POS Profile đổi (hỏi mỗi 4 giây,
	// lib/changes.ts) + lưới an toàn. Trước 2026-11-25: get_buzzers mỗi 5 giây khi modal mở.
	const load = useCallback(async () => {
		try {
			setList((await api.getBuzzers()) || []);
			setError("");
		} catch (err) {
			setError(err instanceof Error ? err.message : String(err));
		}
	}, []);
	usePosRefresh(load, { enabled: open });

	useEffect(() => {
		if (!open) return;
		const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
		window.addEventListener("keydown", onKey);
		return () => window.removeEventListener("keydown", onKey);
	}, [open, onClose]);

	if (!open) return null;

	return (
		<div className="pos-modal-backdrop" onClick={onClose}>
			<div className="pos-modal pos-modal--buzzer" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
				<div className="pos-modal__header">
					<h3>Chọn thẻ bàn</h3>
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
						<div className="pos-empty">Chưa có thẻ bàn nào. Quản lý thêm thẻ trên Desk (Thẻ bàn).</div>
					)}
				</div>
			</div>
		</div>
	);
}