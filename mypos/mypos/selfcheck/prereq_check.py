def check_prereq(quiet=False):
	"""Điều kiện nền để chạy các selfcheck GHI dữ liệu thử trên site mới. CHỈ ĐỌC, không tạo / sửa / xóa gì.

	    bench --site <site> execute mypos.selfcheck.prereq_check.check_prereq

	In từng mục OK / THIẾU (chặn) / CẢNH BÁO (không chặn) kèm cách tạo. Trả về dict:
	    {"ok": bool, "missing": [..], "warnings": [..], "company", "currency", "warehouse", "customer_group", "territory",
	     "mop_cash", "bank_account", "write_off_account", "cost_center", "income_account"}
	`ok` = không thiếu mục chặn nào. `mypos.selfcheck.test_shop.zz_test_shop` dùng kết quả này để dựng quán thử;
	các test ghi dữ liệu SKIP (có lý do) khi `ok` sai.
	"""
	import socket

	import frappe
	from frappe.utils import nowdate

	SETUP = "chạy Setup Wizard của ERPNext (/app/setup-wizard) hoặc tạo trên Desk"
	REQUIRED_ROLES = ("POS CASHIER", "POS KITCHEN", "POS MANAGER")
	MYPOS_DOCTYPES = ("MYPOS Menu", "MYPOS Option Group", "MYPOS Buzzer", "MYPOS Order QR", "MYPOS Banner")

	out = {"ok": False, "missing": [], "warnings": []}

	def say(msg):
		if not quiet:
			print(msg)

	def good(label, detail=""):
		say(f"OK      {label}" + (f": {detail}" if detail else ""))

	def missing(label, how):
		out["missing"].append(label)
		say(f"THIẾU   {label} — cách tạo: {how}")

	def warn(label, how):
		out["warnings"].append(label)
		say(f"CẢNH BÁO {label} — {how}")

	def leaf(doctype, preferred=None):
		if preferred and frappe.db.exists(doctype, {"name": preferred, "is_group": 0}):
			return preferred
		rows = frappe.get_all(doctype, filters={"is_group": 0}, pluck="name", order_by="lft asc", limit=1)
		return rows[0] if rows else None

	try:
		# --- app đã migrate
		for dt in MYPOS_DOCTYPES:
			if not frappe.db.exists("DocType", dt):
				missing(f"DocType {dt}", "bench --site <site> migrate (app mypos chưa nạp)")
		roles = [r for r in REQUIRED_ROLES if not frappe.db.exists("Role", r)]
		if roles:
			missing(f"Role {', '.join(roles)}", "bench --site <site> migrate (after_migrate tạo role)")
		else:
			good("3 role POS", ", ".join(REQUIRED_ROLES))

		# --- Company
		company = frappe.defaults.get_global_default("company") or frappe.db.get_single_value("Global Defaults", "default_company")
		if not company:
			companies = frappe.get_all("Company", pluck="name")
			company = companies[0] if len(companies) == 1 else None
		if not company or not frappe.db.exists("Company", company):
			missing("Company mặc định", SETUP)
			return out
		out["company"] = company
		c = frappe.db.get_value(
			"Company", company,
			["default_currency", "default_receivable_account", "default_income_account", "cost_center", "write_off_account",
			 "round_off_account", "round_off_cost_center", "default_cash_account", "default_bank_account"],
			as_dict=True,
		)
		good("Company mặc định", company)
		out["currency"] = c.default_currency
		if c.default_currency != "VND":
			missing(f"Company dùng tiền VND (hiện {c.default_currency})",
				"MYPOS Menu tra giá cố định currency VND (docs/rules/menu.md §2): dùng Company tiền VND")
		else:
			good("Tiền tệ Company", "VND")
		for field, label in (
			("default_receivable_account", "Tài khoản phải thu mặc định"),
			("default_income_account", "Tài khoản doanh thu mặc định"),
			("cost_center", "Cost Center mặc định"),
			("write_off_account", "Tài khoản Write Off"),
			("round_off_account", "Tài khoản Round Off"),
			("round_off_cost_center", "Cost Center Round Off"),
		):
			if c.get(field):
				good(label, c.get(field))
			else:
				missing(label, f"Company {company} → tab Accounts / Defaults ({SETUP})")
		out["write_off_account"], out["cost_center"], out["income_account"] = (
			c.write_off_account, c.cost_center, c.default_income_account)
		out["bank_account"] = c.default_bank_account or c.default_cash_account
		if out["bank_account"]:
			good("Tài khoản cho Mode of Payment chuyển khoản tạm", out["bank_account"])
		else:
			missing("Company: default_bank_account hoặc default_cash_account", f"Company {company} → Accounts")

		# --- Năm tài chính
		try:
			from erpnext.accounts.utils import get_fiscal_year

			fy = get_fiscal_year(nowdate(), company=company)
			good("Năm tài chính chứa hôm nay", fy[0])
		except Exception:  # noqa: BLE001
			frappe.clear_last_message()
			missing("Năm tài chính (Fiscal Year) chứa ngày hôm nay", f"Desk → Fiscal Year → New, gắn Company ({SETUP})")

		# --- Kho
		wh = frappe.get_all("Warehouse", filters={"company": company, "is_group": 0, "disabled": 0}, pluck="name",
			order_by="creation asc", limit=1)
		if wh:
			out["warehouse"] = wh[0]
			good("Kho (Warehouse lá)", wh[0])
		else:
			missing("Kho (Warehouse không phải nhóm) của Company", SETUP)

		# --- Price List bán (thông tin; quán thử tự tạo Price List riêng)
		spl = frappe.db.get_single_value("Selling Settings", "selling_price_list")
		if spl or frappe.db.exists("Price List", {"selling": 1, "enabled": 1}):
			good("Price List bán", spl or "có")
		else:
			warn("Chưa có Price List bán", "không chặn: quán thử tự tạo Price List riêng; quán thật cần tạo")
		if frappe.db.exists("Currency", "VND") and not frappe.db.get_value("Currency", "VND", "enabled"):
			missing("Currency VND đang tắt", "Desk → Currency → VND → Enabled")

		# --- Mode of Payment Cash có tài khoản cho Company
		mop = frappe.db.get_value("Mode of Payment", {"type": "Cash", "enabled": 1}, "name", order_by="creation asc")
		if mop and frappe.db.get_value("Mode of Payment Account", {"parent": mop, "company": company}, "default_account"):
			out["mop_cash"] = mop
			good("Mode of Payment tiền mặt có tài khoản", mop)
		elif mop:
			missing(f"Mode of Payment {mop}: tài khoản cho Company {company}", f"Desk → Mode of Payment → {mop} → Accounts")
		else:
			missing("Mode of Payment loại Cash", SETUP)

		# --- Customer Group / Territory / Item Group / UOM
		cg = leaf("Customer Group", frappe.db.get_single_value("Selling Settings", "customer_group"))
		(good("Customer Group (lá)", cg) if cg else missing("Customer Group không phải nhóm", SETUP))
		out["customer_group"] = cg
		te = leaf("Territory", frappe.db.get_single_value("Selling Settings", "territory"))
		(good("Territory (lá)", te) if te else missing("Territory không phải nhóm", SETUP))
		out["territory"] = te
		(good("Item Group gốc", "All Item Groups") if frappe.db.exists("Item Group", "All Item Groups")
			else missing("Item Group 'All Item Groups'", SETUP))
		(good("UOM", "Nos") if frappe.db.exists("UOM", "Nos") else missing("UOM 'Nos'", "Desk → UOM → New: Nos"))

		# --- POS Settings: app dùng POS Invoice (đóng ca gộp POS Invoice)
		inv_type = frappe.db.get_single_value("POS Settings", "invoice_type")
		if inv_type == "POS Invoice":
			good("POS Settings → Invoice Type", inv_type)
		else:
			missing(f"POS Settings → Invoice Type = POS Invoice (hiện {inv_type!r})", "Desk → POS Settings → Invoice Type = POS Invoice → Save")

		# --- Redis / scheduler / socketio
		try:
			frappe.cache.set_value("mypos_prereq_ping", 1, expires_in_sec=10)
			ok_redis = frappe.cache.get_value("mypos_prereq_ping") == 1
		except Exception:  # noqa: BLE001
			ok_redis = False
		(good("Redis cache") if ok_redis else missing("Redis cache", "bench start (redis_cache) / kiểm redis_cache trong common_site_config"))
		try:
			from frappe.utils.scheduler import is_scheduler_inactive

			(warn("Scheduler đang tắt", "bench --site <site> enable-scheduler (cron tự hủy Draft quá hạn)") if is_scheduler_inactive()
				else good("Scheduler", "đang bật"))
		except Exception as e:  # noqa: BLE001
			warn("Không đọc được trạng thái scheduler", repr(e))
		port = frappe.conf.get("socketio_port") or 9000
		try:
			with socket.create_connection(("localhost", int(port)), timeout=1):
				good("socket.io", f"localhost:{port} mở")
		except OSError:
			warn(f"socket.io localhost:{port} không mở", "không chặn: màn POS tự poll; chạy bench start để có realtime")

		out["ok"] = not out["missing"]
		return out
	finally:
		say(f"KẾT QUẢ: {'ĐỦ điều kiện nền' if out.get('ok') else 'THIẾU ' + str(len(out['missing'])) + ' mục'}"
			f", {len(out['warnings'])} cảnh báo")
