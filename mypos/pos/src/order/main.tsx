import React from "react";
import ReactDOM from "react-dom/client";
import OrderApp from "./OrderApp";
import "./order.css";

// Entry của web đặt món QR (build riêng: vite.order.config.ts -> public/order/order.js).
const container = document.getElementById("root");

if (container) {
	ReactDOM.createRoot(container).render(
		<React.StrictMode>
			<OrderApp />
		</React.StrictMode>
	);
}
