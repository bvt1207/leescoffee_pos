def check_sidebar():
	"""Sidebar "MYPOS" (DocType `Sidebar`, Frappe >= 16.50) khớp app. CHỈ ĐỌC, không tạo / sửa / xóa dữ liệu.

	Chạy SAU migrate:
	    bench --site <site> execute mypos.selfcheck.sidebar_check.check_sidebar
	Kiểm: Sidebar "MYPOS" tồn tại; module = MYPOS; app = mypos; standard = 1; mọi mục là Workspace đang tồn tại;
	không có mục DocType MYPOS Option Group / Order QR / Menu; số mục = số workspace app đang ship; không trùng link_to;
	không có Sidebar nào khác của module MYPOS (sidebar tự sinh / bản chuyển đổi); thứ tự mục Admin, Manager, Cashier, Kitchen
	(thay cho sidebar_order_check riêng).
	"""
	import os

	import frappe

	SIDEBAR = "MYPOS"
	MODULE = "MYPOS"
	APP = "mypos"
	FORBIDDEN = {"MYPOS Option Group", "MYPOS Order QR", "MYPOS Menu"}
	# Thứ tự = điểm đến của ô MYPOS trên màn Apps (mục đầu tiên user được xem): quyết định chủ dự án 2026-11-27.
	EXPECTED_ORDER = ["MYPOS Admin", "MYPOS Manager", "MYPOS Cashier", "MYPOS Kitchen"]

	results = []

	def ok(cond, label, detail=""):
		results.append(bool(cond))
		print(f"{'PASS' if cond else 'FAIL'} {label}" + (f" — {detail}" if detail and not cond else ""))

	try:
		if not frappe.db.exists("DocType", "Sidebar"):
			ok(False, "DocType Sidebar tồn tại (Frappe >= 16.50)")
			return
		exists = frappe.db.exists("Sidebar", SIDEBAR)
		ok(exists, f'Sidebar "{SIDEBAR}" tồn tại')
		if not exists:
			return
		sb = frappe.get_doc("Sidebar", SIDEBAR)
		ok(sb.module == MODULE, f"module = {MODULE}", f"thực tế {sb.module!r}")
		ok(sb.app == APP, f"app = {APP}", f"thực tế {sb.app!r}")
		ok(int(sb.standard or 0) == 1, "standard = 1", f"thực tế {sb.standard!r}")

		links = [r for r in sb.items if (r.type or "Link") == "Link"]
		non_ws = [f"{r.label} ({r.link_type})" for r in links if r.link_type != "Workspace"]
		ok(not non_ws, "mọi mục là link Workspace", f"mục khác: {non_ws}")
		missing = [r.link_to for r in links if r.link_type == "Workspace" and not frappe.db.exists("Workspace", r.link_to)]
		ok(not missing, "mọi link_to là Workspace đang tồn tại", f"không tồn tại: {missing}")
		bad = [r.link_to for r in links if r.link_to in FORBIDDEN]
		ok(not bad, "không có mục MYPOS Option Group / Order QR / Menu", f"có: {bad}")
		targets = [r.link_to for r in links]
		ordered = [r.link_to for r in sorted(links, key=lambda r: r.idx)]
		ok(ordered == EXPECTED_ORDER, "thứ tự mục: Admin, Manager, Cashier, Kitchen", f"thực tế {ordered}")
		dups = sorted({t for t in targets if targets.count(t) > 1})
		ok(not dups, "không trùng link_to", f"trùng: {dups}")

		ws_dir = os.path.join(frappe.get_module_path(MODULE), "workspace")
		shipped = sorted(
			d for d in os.listdir(ws_dir) if os.path.isfile(os.path.join(ws_dir, d, f"{d}.json"))
		) if os.path.isdir(ws_dir) else []
		ok(len(links) == len(shipped), "số mục = số workspace app ship",
			f"{len(links)} mục / {len(shipped)} workspace ({shipped})")
		ws_names = {frappe.scrub(t) for t in targets}
		ok(ws_names == set(shipped), "mục sidebar khớp đúng các workspace ship", f"{sorted(ws_names)} vs {shipped}")

		others = frappe.get_all("Sidebar", filters={"module": MODULE, "name": ["!=", SIDEBAR]}, fields=["name", "standard"])
		ok(not others, f"không có Sidebar khác của module {MODULE}", f"có: {others}")
		print("INFO mục:", [(r.idx, r.label, r.link_to, r.icon) for r in sb.items])
	finally:
		passed = sum(results)
		print(f"KẾT QUẢ: {passed}/{len(results)} PASS")
