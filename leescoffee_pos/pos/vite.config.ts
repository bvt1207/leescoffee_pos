import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// Build ra leescoffee_pos/public/pos/ → Frappe phục vụ tại
// /assets/leescoffee_pos/pos/ (symlink sites/assets/leescoffee_pos -> apps/leescoffee_pos/public)
export default defineConfig({
	base: "/assets/leescoffee_pos/pos/",
	plugins: [react()],
	resolve: {
		alias: {
			"@": fileURLToPath(new URL("./src", import.meta.url)),
		},
	},
	build: {
		outDir: fileURLToPath(new URL("../public/pos", import.meta.url)),
		emptyOutDir: true,
		rollupOptions: {
			input: fileURLToPath(new URL("./pos.html", import.meta.url)),
			output: {
				// Tên file cố định để www/pos.html trỏ tới không phải sửa sau mỗi lần build
				entryFileNames: "pos.js",
				chunkFileNames: "pos-[name].js",
				assetFileNames: "pos.[ext]",
			},
		},
	},
	server: {
		port: 5173,
		// Dùng khi chạy `npm run dev`: chuyển tiếp API về bench thật
		proxy: {
			"/api": {
				target: "http://localhost:8000",
				changeOrigin: true,
			},
		},
	},
});
