import { useToasts } from "../store/toasts";

/** Cột toast dùng chung (gắn MỘT lần ở App). Toast mới nhất ở dưới; tự xuống dòng, không cắt chữ, không đè nhau. */
export default function ToastStack() {
	const toasts = useToasts((s) => s.toasts);
	const dismiss = useToasts((s) => s.dismiss);
	if (!toasts.length) return null;
	return (
		<div className="pos-toasts" role="status" aria-live="polite">
			{toasts.map((t) =>
				t.dismissible ? (
					<button key={t.id} type="button" className="pos-toast pos-toast--dismiss" onClick={() => dismiss(t.id)}>
						{t.text}
					</button>
				) : (
					<div key={t.id} className="pos-toast">
						{t.text}
					</div>
				)
			)}
		</div>
	);
}
