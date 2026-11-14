import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// Build RIÊNG cho web đặt món QR của khách (src/order) -> leescoffee_pos/public/order/
// Frappe phục vụ tại /assets/leescoffee_pos/order/order.js + order.css (www/mypos_order.html).
// Tách khỏi vite.config.ts (màn nhân viên) để 2 bundle độc lập, không chia chunk/CSS dùng chung
// (trang shell của Frappe chỉ nạp đúng 1 file js + 1 file css cố định).
export default defineConfig({
	base: "/assets/leescoffee_pos/order/",
	plugins: [react()],
	publicDir: false,
	resolve: {
		alias: {
			"@": fileURLToPath(new URL("./src", import.meta.url)),
		},
	},
	build: {
		outDir: fileURLToPath(new URL("../public/order", import.meta.url)),
		emptyOutDir: true,
		cssCodeSplit: false,
		rollupOptions: {
			input: fileURLToPath(new URL("./order.html", import.meta.url)),
			output: {
				entryFileNames: "order.js",
				chunkFileNames: "order-[name].js",
				assetFileNames: "order.[ext]",
				inlineDynamicImports: true,
			},
		},
	},
	server: {
		port: 5174,
		proxy: {
			"/api": { target: "http://localhost:8000", changeOrigin: true },
		},
	},
});
