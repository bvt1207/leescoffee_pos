import { useEffect, useRef } from "react";

/**
 * Poll an toàn cho web khách:
 * - Một chuỗi setTimeout duy nhất: lần sau chỉ hẹn khi lần trước xong (không chồng request khi server chậm).
 * - Tab ẩn -> dừng; tab hiện lại -> chạy ngay 1 lần rồi tiếp tục.
 * - Lỗi -> giãn dần (interval × 2^lần lỗi, tối đa maxBackoffMs); thành công -> về interval.
 * - enabled = false hoặc unmount -> hủy hẹn giờ + abort request đang chạy.
 * `task` đọc qua ref nên đổi hàm (closure mới mỗi render) KHÔNG khởi động lại vòng poll.
 */
export function usePolling(
	task: (signal: AbortSignal) => Promise<void>,
	enabled: boolean,
	intervalMs: number,
	{ immediate = true, maxBackoffMs = 30000 }: { immediate?: boolean; maxBackoffMs?: number } = {}
) {
	const taskRef = useRef(task);
	taskRef.current = task;

	useEffect(() => {
		if (!enabled) return;
		let stopped = false;
		let timer: number | undefined;
		let ctrl: AbortController | null = null;
		let failures = 0;

		const schedule = () => {
			if (stopped || document.visibilityState !== "visible") return;
			const delay = failures ? Math.min(intervalMs * 2 ** failures, maxBackoffMs) : intervalMs;
			timer = window.setTimeout(run, delay);
		};

		const run = async () => {
			timer = undefined;
			if (stopped || ctrl || document.visibilityState !== "visible") return;
			ctrl = new AbortController();
			const mine = ctrl;
			try {
				await taskRef.current(mine.signal);
				failures = 0;
			} catch {
				if (mine.signal.aborted) return;
				failures += 1;
			} finally {
				if (ctrl === mine) ctrl = null;
			}
			schedule();
		};

		const onVisibility = () => {
			window.clearTimeout(timer);
			timer = undefined;
			if (document.visibilityState === "visible") void run();
		};

		document.addEventListener("visibilitychange", onVisibility);
		if (immediate) void run();
		else schedule();

		return () => {
			stopped = true;
			window.clearTimeout(timer);
			ctrl?.abort();
			document.removeEventListener("visibilitychange", onVisibility);
		};
	}, [enabled, intervalMs, immediate, maxBackoffMs]);
}
