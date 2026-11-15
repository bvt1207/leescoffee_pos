"""Đổi tên 3 DocType: Leescoffee Menu Item / Menu / Buzzer -> MYPOS Menu Item / Menu / Buzzer.

Chạy ở [pre_model_sync] (TRƯỚC khi sync DocType từ JSON), để DocType mới nhận lại
bảng + dữ liệu cũ thay vì sync tạo DocType rỗng.

- Chỉ dùng frappe.rename_doc + SQL; KHÔNG import code DocType mới.
- Idempotent:
  * cũ có, mới chưa có -> rename_doc rồi sửa phần còn sót bằng SQL;
  * cũ không có (site cài mới, hoặc đã đổi tên) -> bỏ qua rename, chỉ chạy lại bước SQL (0 dòng);
  * CÓ CẢ cũ lẫn mới -> dừng, báo lỗi, KHÔNG xóa gì (quyết định Van 2026-11-15).
- In số bản ghi trước/sau mỗi DocType và số POS Invoice có thẻ rung.
Thứ tự: bảng con Menu Item trước, rồi Menu (để cập nhật parenttype bảng con), rồi Buzzer.
"""

import frappe

RENAMES = [
	("Leescoffee Menu Item", "MYPOS Menu Item"),
	("Leescoffee Menu", "MYPOS Menu"),
	("Leescoffee Buzzer", "MYPOS Buzzer"),
]

LINK_FIELDTYPES = ("Link", "Table", "Table MultiSelect")
# Bảng con của DocType (parent = tên DocType)
DOCTYPE_CHILD_TABLES = ("DocField", "DocPerm", "DocType Link", "DocType Action", "DocType State")


def _exists(dt):
	return bool(frappe.db.exists("DocType", dt))


def _count(dt):
	# cached=False: sau RENAME TABLE, danh sách bảng cache (client_cache "db_tables") có thể cũ.
	if not frappe.db.table_exists(dt, cached=False):
		return None
	return frappe.db.sql(f"SELECT COUNT(*) FROM `tab{dt}`")[0][0]


def _invoices_with_buzzer():
	if not frappe.db.has_column("POS Invoice", "buzzer"):
		return None
	return frappe.db.sql("SELECT COUNT(*) FROM `tabPOS Invoice` WHERE IFNULL(buzzer, '') != ''")[0][0]


def _sql(stats, label, query, values):
	frappe.db.sql(query, values)
	n = frappe.db.sql("SELECT ROW_COUNT()")[0][0] or 0
	if n:
		stats.append(f"  {label}: {n} dòng")
	return n


def _fix_leftovers(old, new, stats):
	"""Sửa các chỗ rename_doc có thể bỏ sót. Chạy lại không đổi gì."""
	for table in DOCTYPE_CHILD_TABLES:
		if frappe.db.table_exists(table):
			_sql(stats, f"{table}.parent", f"UPDATE `tab{table}` SET parent = %s WHERE parent = %s AND parenttype = 'DocType'", (new, old))

	for table in ("DocField", "Custom Field"):
		_sql(
			stats,
			f"{table}.options",
			f"UPDATE `tab{table}` SET options = %s WHERE options = %s AND fieldtype IN %s",
			(new, old, LINK_FIELDTYPES),
		)

	_sql(stats, "Custom Field.dt", "UPDATE `tabCustom Field` SET dt = %s WHERE dt = %s", (new, old))
	_sql(stats, "Property Setter.doc_type", "UPDATE `tabProperty Setter` SET doc_type = %s WHERE doc_type = %s", (new, old))
	_sql(
		stats,
		"Property Setter.value (options)",
		"UPDATE `tabProperty Setter` SET value = %s WHERE property = 'options' AND value = %s",
		(new, old),
	)

	# Custom DocPerm: chỉ chuyển dòng không trùng (role, permlevel, if_owner) với dòng đã mang tên mới,
	# để không nhân bản. Dòng trùng giữ nguyên, chỉ báo (không xóa).
	if frappe.db.table_exists("Custom DocPerm"):
		for row in frappe.db.sql(
			"SELECT name, role, permlevel, if_owner FROM `tabCustom DocPerm` WHERE parent = %s", old, as_dict=True
		):
			dup = frappe.db.sql(
				"SELECT name FROM `tabCustom DocPerm` WHERE parent = %s AND role = %s AND permlevel = %s AND if_owner = %s LIMIT 1",
				(new, row.role, row.permlevel, row.if_owner),
			)
			if dup:
				stats.append(f"  Custom DocPerm {row.name} ({row.role}) trùng dòng tên mới -> giữ nguyên, cần xem tay")
				continue
			_sql(stats, "Custom DocPerm.parent", "UPDATE `tabCustom DocPerm` SET parent = %s WHERE name = %s", (new, row.name))

	for table in ("Workspace Link", "Workspace Shortcut"):
		if frappe.db.table_exists(table):
			_sql(stats, f"{table}.link_to", f"UPDATE `tab{table}` SET link_to = %s WHERE link_to = %s", (new, old))


def execute():
	conflicts = [(old, new) for old, new in RENAMES if _exists(old) and _exists(new)]
	if conflicts:
		frappe.throw(
			"Đổi tên MYPOS: trên DB có CẢ DocType cũ lẫn mới: "
			+ ", ".join(f"'{o}' + '{n}'" for o, n in conflicts)
			+ ". Patch dừng, không xóa gì. Nguyên nhân thường gặp: đã migrate khi chưa có patch hoặc còn thư mục "
			"doctype cũ trên bench. Đối chiếu số bản ghi hai bên rồi xử lý tay trước khi migrate lại."
		)

	if not any(_exists(old) for old, _new in RENAMES) and not any(_exists(new) for _old, new in RENAMES):
		print("[v1_rename_mypos_doctypes] Site chưa có DocType cũ lẫn mới (cài mới) -> bỏ qua.")
		return

	print(f"[v1_rename_mypos_doctypes] POS Invoice có thẻ rung (trước): {_invoices_with_buzzer()}")
	report = []
	for old, new in RENAMES:
		stats = []
		if _exists(old):
			before = _count(old)
			# Chữ ký frappe.rename_doc v16 (frappe/__init__.py): doctype, old, new, force, merge, *,
			# ignore_if_exists, show_alert, rebuild_search — KHÔNG có ignore_permissions. Migrate chạy dưới
			# Administrator (DocType.before_rename yêu cầu Administrator; check_developer_mode bỏ qua khi in_patch,
			# after_rename không dời thư mục khi in_patch). rebuild_search=False: không enqueue job khi migrate.
			frappe.rename_doc("DocType", old, new, force=True, merge=False, show_alert=False, rebuild_search=False)
			frappe.db.commit()
			report.append(f"{old} -> {new}: đã đổi tên, bản ghi trước {before}, sau {_count(new)}")
		else:
			report.append(f"{new}: đã có sẵn (không đổi tên), bản ghi {_count(new)}")
		if _exists(new):
			_fix_leftovers(old, new, stats)
		report.extend(stats)

	if frappe.db.table_exists("MYPOS Menu Item", cached=False):
		stats = []
		_sql(
			stats,
			"MYPOS Menu Item.parenttype",
			"UPDATE `tabMYPOS Menu Item` SET parenttype = 'MYPOS Menu' WHERE parenttype = 'Leescoffee Menu'",
			(),
		)
		report.extend(stats)

	frappe.db.commit()
	frappe.clear_cache()
	report.append(f"POS Invoice có thẻ rung (sau): {_invoices_with_buzzer()}")
	for line in report:
		print(f"[v1_rename_mypos_doctypes] {line}")
