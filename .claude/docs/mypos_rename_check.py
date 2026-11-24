# Kiểm tra đổi tên DocType Leescoffee Menu / Menu Item / Buzzer -> MYPOS Menu / Menu Item / Buzzer.
# Dán cả file vào `bench --site <site> console`.
#
# 1) TRƯỚC khi copy file:   mypos_rename_count()            -> ghi lại dict in ra
# 2) Sau migrate lần 1:     run_mypos_rename_check(before={...dict bước 1...})
#                           (lưu ảnh chụp vào sites/<site>/private/mypos_rename_snapshot.json)
# 3) bench migrate lần 2, mở console mới, dán lại file:
#                           run_mypos_rename_check(before={...}, second_migrate=True, run_selftests=False)
#    -> so ảnh chụp: không đổi, không nhân bản.
# Muốn chạy 2 bộ self-test cũ: dán order_qr_selftest.py + order_history_selftest.py TRƯỚC file này.
#
# Tham số: branch (mặc định Branch của POS Profile đang bật đầu tiên), cashier_user / manager_user
# (mặc định user đang bật có role tương ứng, không phải Administrator).

# Mọi hằng đặt TRONG hàm (dán vào console không phụ thuộc biến toàn cục).


def mypos_rename_count():
	"""Đếm bản ghi, đọc được cả tên cũ lẫn mới. Chạy TRƯỚC khi copy file."""
	import frappe

	def cnt(old, new):
		for dt in (old, new):
			if frappe.db.exists("DocType", dt) and frappe.db.table_exists(dt, cached=False):
				return frappe.db.sql(f"SELECT COUNT(*) FROM `tab{dt}`")[0][0]
		return None

	out = {
		"menu": cnt("Leescoffee Menu", "MYPOS Menu"),
		"menu_item": cnt("Leescoffee Menu Item", "MYPOS Menu Item"),
		"buzzer": cnt("Leescoffee Buzzer", "MYPOS Buzzer"),
		"inv_buzzer": frappe.db.sql("SELECT COUNT(*) FROM `tabPOS Invoice` WHERE IFNULL(buzzer, '') != ''")[0][0],
	}
	print(out)
	return out


def run_mypos_rename_check(before=None, branch=None, cashier_user=None, manager_user=None, second_migrate=False, run_selftests=True):
	import contextlib
	import io
	import json
	import os
	import re
	import traceback

	import frappe

	from leescoffee_pos.leescoffee_pos.api import pos_api as P
	from leescoffee_pos.patches import v1_create_pos_roles as R

	OLD_NEW = [
		("Leescoffee Menu", "MYPOS Menu"),
		("Leescoffee Menu Item", "MYPOS Menu Item"),
		("Leescoffee Buzzer", "MYPOS Buzzer"),
	]
	# Trùng Custom DocPerm của role chuẩn ERPNext trên 2 DocType này có từ 08/11 -> chỉ cảnh báo (WARN).
	WARN_DUP_ROLES = ("System Manager", "Manager", "Sales User")
	WARN_DUP_DOCTYPES = ("MYPOS Menu", "MYPOS Buzzer")

	admin = frappe.session.user
	results = []
	warns = []
	new_names = [n for _o, n in OLD_NEW]
	old_names = [o for o, _n in OLD_NEW]

	def check(label, ok, detail=""):
		results.append(bool(ok))
		print(("PASS " if ok else "FAIL ") + label + (f"  [{detail}]" if detail else ""))

	def q1(sql, values=()):
		return frappe.db.sql(sql, values)[0][0]

	def as_user(user, fn, *a, **kw):
		frappe.set_user(user)
		try:
			return fn(*a, **kw)
		finally:
			frappe.set_user(admin)

	def user_with_role(role):
		rows = frappe.db.sql(
			"""SELECT u.name FROM `tabUser` u JOIN `tabHas Role` hr ON hr.parent = u.name AND hr.parenttype = 'User'
			WHERE hr.role = %s AND u.enabled = 1 AND u.name NOT IN ('Administrator', 'Guest') ORDER BY u.creation LIMIT 1""",
			role,
		)
		return rows[0][0] if rows else None

	def snapshot():
		return {
			"counts": {dt: q1(f"SELECT COUNT(*) FROM `tab{dt}`") for dt in new_names},
			"inv_buzzer": q1("SELECT COUNT(*) FROM `tabPOS Invoice` WHERE IFNULL(buzzer, '') != ''"),
			"workspace_links": [
				list(r)
				for r in frappe.db.sql(
					"SELECT idx, type, label, link_to, link_count FROM `tabWorkspace Link` WHERE parent = 'leescoffee_pos' ORDER BY idx"
				)
			],
			"custom_docperm": sorted(
				[list(r) for r in frappe.db.sql(
					"""SELECT parent, role, permlevel, if_owner, `select`, `read`, `write`, `create` FROM `tabCustom DocPerm`
					WHERE parent IN %s ORDER BY parent, role""",
					(tuple(new_names),),
				)]
			),
			"docfields": {dt: q1("SELECT COUNT(*) FROM `tabDocField` WHERE parent = %s", dt) for dt in new_names},
			"modified": {dt: str(frappe.db.get_value("DocType", dt, "modified")) for dt in new_names},
			"buzzer_options": frappe.db.get_value("Custom Field", "POS Invoice-buzzer", "options"),
		}

	try:
		# ---------- 1. DocType cũ/mới ----------
		for old, new in OLD_NEW:
			check(f"R1 DocType cũ '{old}' không còn", frappe.db.exists("DocType", old) is None)
			meta = frappe.db.get_value("DocType", new, ["name", "module", "istable"], as_dict=True)
			check(f"R2 DocType mới '{new}' có, module Leescoffee POS", bool(meta) and meta.module == "Leescoffee POS", str(meta))
		check("R2b MYPOS Menu Item là bảng con", frappe.db.get_value("DocType", "MYPOS Menu Item", "istable") == 1)
		check("R2c Bảng tab cũ không còn", not any(frappe.db.table_exists(o, cached=False) for o in old_names))

		# ---------- 2. Số bản ghi trước/sau ----------
		now = {
			"menu": q1("SELECT COUNT(*) FROM `tabMYPOS Menu`"),
			"menu_item": q1("SELECT COUNT(*) FROM `tabMYPOS Menu Item`"),
			"buzzer": q1("SELECT COUNT(*) FROM `tabMYPOS Buzzer`"),
			"inv_buzzer": q1("SELECT COUNT(*) FROM `tabPOS Invoice` WHERE IFNULL(buzzer, '') != ''"),
		}
		if before:
			for k, v in now.items():
				check(f"R3 Số bản ghi {k}: trước {before.get(k)} = sau {v}", before.get(k) == v)
		else:
			print(f"BỎ QUA R3 (không truyền before). Hiện tại: {now}")

		# ---------- 3. Bảng con + Link ----------
		bad_pt = frappe.db.sql(
			"SELECT parenttype, COUNT(*) FROM `tabMYPOS Menu Item` WHERE parenttype != 'MYPOS Menu' OR parentfield != 'items' GROUP BY parenttype"
		)
		check("R4 MYPOS Menu Item: mọi dòng parenttype = 'MYPOS Menu', parentfield = 'items'", not bad_pt, str(bad_pt))
		orphan = q1(
			"SELECT COUNT(*) FROM `tabMYPOS Menu Item` i LEFT JOIN `tabMYPOS Menu` m ON m.name = i.parent WHERE m.name IS NULL"
		)
		check("R4b Không có dòng Menu Item mồ côi", orphan == 0, f"{orphan} dòng")
		check(
			"R5 Custom Field POS Invoice-buzzer options = 'MYPOS Buzzer'",
			frappe.db.get_value("Custom Field", "POS Invoice-buzzer", "options") == "MYPOS Buzzer",
		)
		frappe.clear_cache(doctype="POS Invoice")
		check("R5b Meta POS Invoice.buzzer trỏ MYPOS Buzzer", frappe.get_meta("POS Invoice").get_field("buzzer").options == "MYPOS Buzzer")
		check("R5c MYPOS Menu.items options = 'MYPOS Menu Item'", frappe.get_meta("MYPOS Menu").get_field("items").options == "MYPOS Menu Item")
		dangling = q1(
			"SELECT COUNT(*) FROM `tabPOS Invoice` i LEFT JOIN `tabMYPOS Buzzer` b ON b.name = i.buzzer WHERE IFNULL(i.buzzer, '') != '' AND b.name IS NULL"
		)
		check("R5d Mọi POS Invoice.buzzer trỏ tới thẻ có thật", dangling == 0, f"{dangling} đơn")

		# ---------- 4. Tên cũ còn sót trên DB ----------
		olds = tuple(old_names)
		leftovers = {
			"DocField.options": q1("SELECT COUNT(*) FROM `tabDocField` WHERE options IN %s", (olds,)),
			"DocField.parent": q1("SELECT COUNT(*) FROM `tabDocField` WHERE parent IN %s", (olds,)),
			"DocPerm.parent": q1("SELECT COUNT(*) FROM `tabDocPerm` WHERE parent IN %s", (olds,)),
			"Custom DocPerm.parent": q1("SELECT COUNT(*) FROM `tabCustom DocPerm` WHERE parent IN %s", (olds,)),
			"Custom Field.options/dt": q1("SELECT COUNT(*) FROM `tabCustom Field` WHERE options IN %s OR dt IN %s", (olds, olds)),
			"Property Setter": q1("SELECT COUNT(*) FROM `tabProperty Setter` WHERE doc_type IN %s OR value IN %s", (olds, olds)),
			"Workspace Link.link_to": q1("SELECT COUNT(*) FROM `tabWorkspace Link` WHERE link_to IN %s", (olds,)),
			"Workspace Shortcut.link_to": q1("SELECT COUNT(*) FROM `tabWorkspace Shortcut` WHERE link_to IN %s", (olds,)),
		}
		check("R6 Không còn tên cũ ở DocField/DocPerm/Custom DocPerm/Custom Field/Property Setter/Workspace", not any(leftovers.values()), str({k: v for k, v in leftovers.items() if v}))
		# Chuỗi cũ trong script/report người dùng tạo tay: rename_doc KHÔNG sửa code -> chỉ liệt kê, không tính FAIL.
		manual = []
		for dt, col in (("Client Script", "script"), ("Server Script", "script"), ("Report", "query"), ("Print Format", "html"), ("Notification", "message")):
			if frappe.db.table_exists(dt) and frappe.db.has_column(dt, col):
				for (name,) in frappe.db.sql(f"SELECT name FROM `tab{dt}` WHERE `{col}` LIKE %s OR `{col}` LIKE %s", ("%Leescoffee Menu%", "%Leescoffee Buzzer%")):
					manual.append(f"{dt}: {name}")
		print("THÔNG TIN: chuỗi tên cũ trong script/report tạo tay (cần sửa tay): " + (", ".join(manual) or "không có"))

		# ---------- 5. Quyền 3 role ----------
		for role, perms in R.PERMS.items():
			for dt in new_names:
				if dt not in perms:
					continue
				rows = frappe.db.sql(
					"""SELECT `select`, `read`, `write`, `create` FROM `tabCustom DocPerm`
					WHERE parent = %s AND role = %s AND permlevel = 0""",
					(dt, role),
					as_dict=True,
				)
				ok = len(rows) == 1 and all(rows[0].get(p) == 1 for p in perms[dt])
				check(f"R7 Custom DocPerm {role} / {dt}: đúng 1 dòng, có {perms[dt]}", ok, str(rows))
		# R7b: trùng theo (parent, role, permlevel), in tên dòng. Role chuẩn ERPNext trên Menu/Buzzer -> WARN.
		dups = frappe.db.sql(
			"""SELECT parent, role, permlevel, COUNT(*) c,
				GROUP_CONCAT(name ORDER BY creation, name SEPARATOR ', ') names
			FROM `tabCustom DocPerm` WHERE parent IN %s
			GROUP BY parent, role, permlevel HAVING c > 1""",
			(tuple(new_names),),
			as_dict=True,
		)
		hard = []
		for d in dups:
			line = f"{d.parent} / {d.role} / permlevel {d.permlevel}: {d.c} dòng ({d.names})"
			if d.role in WARN_DUP_ROLES and d.parent in WARN_DUP_DOCTYPES:
				warns.append(line)
				print("WARN R7b trùng Custom DocPerm (role chuẩn ERPNext, có từ 08/11): " + line)
			else:
				hard.append(line)
		check("R7b Không nhân bản Custom DocPerm (ngoài các dòng WARN)", not hard, "; ".join(hard))

		# ---------- 6. API màn nhân viên ----------
		profile_name = None
		if branch:
			profile_name = frappe.db.get_value("POS Profile", {"branch": branch, "disabled": 0}, "name")
		else:
			row = frappe.get_all("POS Profile", filters={"disabled": 0, "branch": ["is", "set"]}, fields=["name", "branch"], limit=1)
			if row:
				profile_name, branch = row[0].name, row[0].branch
		profile = frappe.get_doc("POS Profile", profile_name) if profile_name else None
		check("R8 Có POS Profile đang bật có branch", bool(profile), str(branch))

		if profile:
			menus = P.get_menu_items()
			items = [it for m in menus for it in m.get("items", [])]
			check("R8a get_menu_items trả menu có món", bool(items), f"{len(menus)} menu, {len(items)} món")
			# create_draft_order bắt buộc price_list (_require_price_list): lấy từ get_menu_items()[0]["price_list"].
			menu_price_list = menus[0].get("price_list") if menus else None
			items = menus[0].get("items", []) if menus else []
			check("R8c Menu đầu tiên có price_list", bool(menu_price_list), str(menu_price_list))
			buzzers = P.get_buzzers(branch)
			check("R8b get_buzzers chạy, có thẻ của chi nhánh", bool(buzzers), f"{len(buzzers)} thẻ")

			opening = frappe.get_all(
				"POS Opening Entry",
				filters={"pos_profile": profile.name, "status": "Open", "docstatus": 1},
				fields=["user"],
				order_by="period_start_date desc",
				limit=1,
			)
			free = next((b for b in buzzers if b.get("available")), None)
			# create_draft_order / cancel_draft_order cần POS CASHIER / POS MANAGER / System Manager / Administrator.
			sale_ok = bool(opening) and (opening[0].user == "Administrator" or bool(
				set(frappe.get_roles(opening[0].user)) & {"POS CASHIER", "POS MANAGER", "System Manager"}))
			if not opening or not free or not items or not menu_price_list or not sale_ok:
				print(f"BỎ QUA R9 (tạo đơn Dine In): ca mở={bool(opening)}, thẻ trống={bool(free)}, món menu đầu={bool(items)}, "
					f"price_list={menu_price_list}, người mở ca có role bán hàng={sale_ok}")
			else:
				cashier = opening[0].user
				it = items[0]
				opts = []
				for g in it.get("option_groups", []):
					if g.get("required") and g.get("values"):
						dv = next((v["label"] for v in g["values"] if v.get("is_default")), g["values"][0]["label"])
						opts.append({"group": g["name"], "value": dv})
				cart = [{"item_code": it["sizes"][0]["item_code"], "qty": 1, "options": opts}]
				# Khách TẠM (2026-11-24): đơn thử chọn khách rõ, không phụ thuộc Khách vãng lai của POS Profile thật.
				_wi = frappe.new_doc("Customer")
				_wi.customer_name = f"ZZTEST WI Rename {frappe.generate_hash(length=6)}"
				_wi.customer_type = "Individual"
				_wi.customer_group = frappe.db.get_single_value("Selling Settings", "customer_group") or "Individual"
				_wi.territory = frappe.db.get_single_value("Selling Settings", "territory") or "All Territories"
				_wi.insert(ignore_permissions=True)
				frappe.db.commit()
				inv_name = None
				try:
					r = as_user(cashier, P.create_draft_order, json.dumps(cart), "Dine In", customer_name=_wi.name, branch_name=branch, price_list=menu_price_list, buzzer=free["name"])
					inv_name = r["invoice_name"]
					check("R9a create_draft_order Dine In gán thẻ rung", r.get("buzzer_number") == free["buzzer_number"], f"{inv_name} thẻ {r.get('buzzer_number')}")
					o = next((x for x in as_user(cashier, P.get_orders, "draft") if x["name"] == inv_name), None)
					check("R9b get_orders hiện số thẻ", bool(o) and o.get("buzzer_number") == free["buzzer_number"])
					d = as_user(cashier, P.get_order_detail, inv_name)
					check("R9c get_order_detail hiện số thẻ", d.get("buzzer_number") == free["buzzer_number"])
					held = next((b for b in as_user(cashier, P.get_buzzers, branch) if b["name"] == free["name"]), {})
					check("R9d get_buzzers: thẻ đang giữ cho đơn vừa tạo", held.get("used_by") == inv_name and not held.get("available"))
				except Exception:
					check("R9 Lỗi ngoài dự kiến khi tạo đơn Dine In", False)
					traceback.print_exc()
				finally:
					if inv_name and frappe.db.exists("POS Invoice", inv_name):
						try:
							as_user(cashier, P.cancel_draft_order, inv_name, 1)
						except Exception:
							frappe.delete_doc("POS Invoice", inv_name, force=True, ignore_permissions=True)
					frappe.db.commit()
					# Dọn khách tạm: đơn thử đã hủy (Cancelled, không xóa từ 2026-11-23) còn tham chiếu khách -> xóa đơn thử trước.
					if inv_name and frappe.db.get_value("POS Invoice", inv_name, "docstatus") == 2:
						frappe.delete_doc("POS Invoice", inv_name, force=True, ignore_permissions=True)
					if frappe.db.exists("Customer", _wi.name):
						frappe.delete_doc("Customer", _wi.name, force=True, ignore_permissions=True)
					frappe.db.commit()
				check("R9e Đã hủy đơn thử, thẻ trống lại", not frappe.db.exists("POS Invoice", inv_name or "-") and
					next((b for b in P.get_buzzers(branch) if b["name"] == free["name"]), {}).get("available"))

		try:
			k = P.get_kitchen_orders()
			bad = [o.get("name") for o in k if o.get("buzzer") and not o.get("buzzer_number")]
			check("R10a get_kitchen_orders chạy, đơn có thẻ đều có số thẻ", not bad, f"{len(k)} đơn")
			sb = P.get_status_board()
			check("R10b get_status_board chạy", sb is not None)
		except Exception:
			check("R10 Lỗi ngoài dự kiến ở màn pha chế", False)
			traceback.print_exc()
		qr_with_buzzer = q1("SELECT COUNT(*) FROM `tabPOS Invoice` WHERE order_channel = 'QR' AND IFNULL(buzzer, '') != ''")
		check("R10c Đơn QR không có thẻ rung", qr_with_buzzer == 0, f"{qr_with_buzzer} đơn")

		# ---------- 7. User thường vào workspace ----------
		users = [
			("POS CASHIER", cashier_user or user_with_role("POS CASHIER")),
			("POS MANAGER", manager_user or user_with_role("POS MANAGER")),
		]
		for role, u in users:
			if not u:
				print(f"BỎ QUA R11 {role}: không có user đang bật có role này")
				continue
			for dt in ("MYPOS Menu", "MYPOS Buzzer"):
				check(f"R11a {u} ({role}) có quyền Read {dt}", frappe.has_permission(dt, "read", user=u))
			try:
				# v16: frappe.desk.desktop không có get_workspace_sidebar_items. Workspace(...) ném PermissionError
				# khi module "Leescoffee POS" không nằm trong allowed_modules của user (đúng lỗi cần bắt).
				from frappe.desk.desktop import Workspace, get_desktop_page

				pg = {"name": "leescoffee_pos", "title": "leescoffee_pos"}
				try:
					ws = as_user(u, Workspace, pg, True)
					check(f"R11b {u} vào được workspace leescoffee_pos (module được phép, is_permitted)", as_user(u, ws.is_permitted))
				except frappe.PermissionError:
					check(f"R11b {u} vào được workspace leescoffee_pos", False, "PermissionError: module không được phép")
				page = as_user(u, get_desktop_page, json.dumps(pg))
				links = [l.get("link_to") for c in (page.get("cards") or {}).get("items", []) for l in c.get("links", [])]
				check(f"R11c {u} thấy 2 link MYPOS Menu + MYPOS Buzzer trong workspace", {"MYPOS Menu", "MYPOS Buzzer"} <= set(links), str(links))
			except (ImportError, AttributeError, TypeError) as e:
				print(f"KHÔNG KIỂM ĐƯỢC R11b/R11c bằng API ({e}) -> kiểm tay: đăng nhập {u}, mở /desk/leescoffee_pos")
			except Exception:
				check(f"R11 {u} lỗi khi mở workspace", False)
				traceback.print_exc()

		# ---------- 8. Idempotent + migrate lần 2 ----------
		from leescoffee_pos.patches import v1_rename_mypos_doctypes as RN

		buf = io.StringIO()
		with contextlib.redirect_stdout(buf):
			RN.execute()
		out = buf.getvalue()
		print(out.rstrip())
		check("R12a Chạy lại patch đổi tên: không đổi tên, không sửa dòng nào", "đã đổi tên" not in out and " dòng" not in out)

		path = frappe.get_site_path("private", "mypos_rename_snapshot.json")
		snap = snapshot()
		if second_migrate:
			if not os.path.exists(path):
				check("R12b Có ảnh chụp sau migrate lần 1", False, path)
			else:
				with open(path, encoding="utf-8") as f:
					prev = json.load(f)
				diff = [k for k in snap if snap[k] != prev.get(k)]
				check("R12b Migrate lần 2 không đổi gì (số bản ghi, Workspace Link, Custom DocPerm, DocField, modified)", not diff, ", ".join(diff))
		else:
			with open(path, "w", encoding="utf-8") as f:
				json.dump(snap, f, ensure_ascii=False, indent=1, default=str)
			print(f"Đã lưu ảnh chụp: {path}  (Workspace Link = {len(snap['workspace_links'])} dòng)")
		check("R12c Workspace Link của leescoffee_pos = 9 dòng", len(snap["workspace_links"]) == 9, str(len(snap["workspace_links"])))
	except Exception:
		check("Lỗi ngoài dự kiến", False)
		traceback.print_exc()
	finally:
		frappe.set_user(admin)

	print(f"\nTổng (đổi tên MYPOS): {sum(results)}/{len(results)} PASS, {len(warns)} WARN")

	# ---------- 9. Hai bộ self-test cũ ----------
	if run_selftests:
		hist = globals().get("run_order_history_selftest")
		if not hist or not globals().get("run_order_qr_selftest"):
			print("Chưa dán order_qr_selftest.py + order_history_selftest.py nên không chạy được 2 bộ cũ.")
			return
		buf = io.StringIO()

		class Tee(io.TextIOBase):
			def write(self, s):
				buf.write(s)
				return sys_stdout.write(s)

		import sys

		sys_stdout = sys.stdout
		with contextlib.redirect_stdout(Tee()):
			hist(branch)
		totals = re.findall(r"Tổng(?: \(lịch sử đơn\))?: (\d+)/(\d+) PASS", buf.getvalue())
		print("\n===== Kết quả 2 bộ cũ =====")
		for got, total in totals:
			print(("ĐỦ PASS " if got == total else "CÓ FAIL ") + f"{got}/{total}")
		if len(totals) < 2:
			print("Không đọc được đủ 2 dòng Tổng, xem log phía trên.")
