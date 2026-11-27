/**
 * Báo "món đã sẵn sàng": rung + 2 tiếng bíp ngắn (Web Audio). Không xin quyền thông báo.
 * Trình duyệt chỉ cho phát âm thanh sau khi người dùng đã chạm vào trang: unlockAudio()
 * được gọi ở lần chạm đầu tiên. Không phát được thì bỏ qua lặng lẽ (vẫn có banner).
 */

let ctx: AudioContext | null = null;

function audioCtor(): typeof AudioContext | null {
	const w = window as unknown as { AudioContext?: typeof AudioContext; webkitAudioContext?: typeof AudioContext };
	return w.AudioContext || w.webkitAudioContext || null;
}

export function unlockAudio(): void {
	try {
		const Ctor = audioCtor();
		if (!Ctor) return;
		if (!ctx) ctx = new Ctor();
		if (ctx.state === "suspended") void ctx.resume();
	} catch {
		/* ignore */
	}
}

function beep(at: number): void {
	if (!ctx) return;
	const osc = ctx.createOscillator();
	const gain = ctx.createGain();
	osc.type = "sine";
	osc.frequency.value = 880;
	gain.gain.setValueAtTime(0.0001, at);
	gain.gain.exponentialRampToValueAtTime(0.3, at + 0.02);
	gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.25);
	osc.connect(gain).connect(ctx.destination);
	osc.start(at);
	osc.stop(at + 0.3);
}

export function notifyReady(): void {
	try {
		navigator.vibrate?.([250, 120, 250]);
	} catch {
		/* ignore */
	}
	try {
		if (ctx && ctx.state === "running") {
			beep(ctx.currentTime);
			beep(ctx.currentTime + 0.4);
		}
	} catch {
		/* ignore */
	}
}
