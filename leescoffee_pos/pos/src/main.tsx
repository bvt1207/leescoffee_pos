import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import App from "./App";
import { PosProvider } from "./lib/pos-context";
import POS from "./pages/POS";
import Orders from "./pages/Orders";
import Table from "./pages/Table";
import "./styles/global.css";

const container = document.getElementById("root");

if (container) {
	ReactDOM.createRoot(container).render(
		<React.StrictMode>
			<BrowserRouter basename="/pos">
				<PosProvider>
					<Routes>
						<Route path="/" element={<App />}>
							<Route index element={<POS />} />
							<Route path="orders" element={<Orders />} />
							<Route path="table" element={<Table />} />
							<Route path="*" element={<Navigate to="/" replace />} />
						</Route>
					</Routes>
				</PosProvider>
			</BrowserRouter>
		</React.StrictMode>
	);
}
