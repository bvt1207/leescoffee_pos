def check_workspace_shortcuts():
	"""Shortcut "Order Status" (/pos/status) + nhãn gọn (bỏ tiền tố "MYPOS") ở 4 workspace MYPOS (2026-11-27). CHỈ ĐỌC.

	Dán CẢ hàm vào `bench --site <site> console` (SAU migrate) rồi gọi: check_workspace_shortcuts()
	Không tạo / sửa / xóa dữ liệu nào.
	"""
	import json
	import os

	import frappe

	MODULE = "MYPOS"
	WORKSPACES = {
		"MYPOS Cashier": "mypos_cashier",
		"MYPOS Kitchen": "mypos_kitchen",
		"MYPOS Manager": "mypos_manager",
		"MYPOS Admin": "mypos_admin",
	}
	ORDER_STATUS = ("Order Status", "/pos/status")
	# Nhãn shortcut mong đợi theo thứ tự hiển thị (content) — quyết định chủ dự án 2026-11-27.
	EXPECTED = {
		"MYPOS Cashier": ["Open MYPOS", "Customer Display", "Order Status"],
		"MYPOS Kitchen": ["Kitchen Screen", "Order Status"],
		"MYPOS Manager": ["Open MYPOS", "Order Status"],
		"MYPOS Admin": ["Open MYPOS", "Kitchen Screen", "Customer Display", "Order Status"],
	}
	ROLES = {
		"MYPOS Cashier": {"POS CASHIER", "System Manager"},
		"MYPOS Kitchen": {"POS KITCHEN", "System Manager"},
		"MYPOS Manager": {"POS MANAGER", "System Manager"},
		"MYPOS Admin": {"System Manager"},
	}
	results = []

	def ok(case, cond, extra=""):
		results.append((case, bool(cond)))
		print(f"{'PASS' if cond else 'FAIL'} {case} {extra}")

	for name, folder in WORKSPACES.items():
		print(f"== {name} ==")
		if not frappe.db.exists("Workspace", name):
			ok(f"{name}: tồn tại", False)
			continue
		doc = frappe.get_doc("Workspace", name)
		pairs = [(s.label, s.url) for s in doc.shortcuts]
		labels = [s.label for s in doc.shortcuts]
		ok(f"{name}: đúng 1 shortcut Order Status", labels.count(ORDER_STATUS[0]) == 1, f"({labels})")
		row = next((s for s in doc.shortcuts if s.label == ORDER_STATUS[0]), None)
		ok(f"{name}: Order Status -> URL /pos/status, type URL",
			row is not None and row.url == ORDER_STATUS[1] and row.type == "URL", f"({row and (row.type, row.url)})")
		ok(f"{name}: không nhãn trùng", len(labels) == len(set(labels)), f"({labels})")
		ok(f"{name}: không còn nhãn tiền tố 'MYPOS ' (trừ 'Open MYPOS')",
			not [l for l in labels if l.startswith("MYPOS ")], f"({labels})")
		blocks = [b["data"]["shortcut_name"] for b in json.loads(doc.content or "[]") if b.get("type") == "shortcut"]
		ok(f"{name}: thứ tự hiển thị = {EXPECTED[name]}", blocks == EXPECTED[name], f"({blocks})")
		ok(f"{name}: mỗi khối shortcut trong content có shortcut cùng nhãn", sorted(blocks) == sorted(labels),
			f"(content {blocks} / shortcuts {labels})")
		roles = {r.role for r in doc.roles}
		ok(f"{name}: roles không đổi {sorted(ROLES[name])}", roles == ROLES[name], f"({sorted(roles)})")
		path = os.path.join(frappe.get_module_path(MODULE), "workspace", folder, f"{folder}.json")
		if os.path.exists(path):
			with open(path, encoding="utf-8") as f:
				data = json.load(f)
			file_pairs = sorted((s.get("label"), s.get("url")) for s in data.get("shortcuts") or [])
			ok(f"{name}: shortcut trong DB khớp file", sorted(pairs) == file_pairs, f"(DB {sorted(pairs)})")
			links = frappe.db.count("Workspace Link", {"parent": name, "parenttype": "Workspace"})
			ok(f"{name}: số Workspace Link khớp file (không nhân đôi)", links == len(data.get("links") or []),
				f"({links} / {len(data.get('links') or [])})")
		else:
			ok(f"{name}: có file {path}", False)

	failed = [c for c, good in results if not good]
	print("== KẾT QUẢ:", "PASS" if not failed else f"FAIL ({len(failed)})", f"— {len(results) - len(failed)}/{len(results)} ==")
	return not failed
