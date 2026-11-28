"""Bước 1: UOM. UOM dạng site (Litre, Millilitre, Gram, Kg) chỉ kiểm tra, không sửa (Q3)."""
import frappe

from seed.common import SeedError, read_csv, to_int

TITLE = "UOM"


def load(ctx, rep, rows=None):
    rows = read_csv("uom.csv") if rows is None else rows
    for r in rows:
        name, whole, source = r["uom"], to_int(r["must_be_whole_number"]), r["source"]
        cur = frappe.db.get_value("UOM", name, ["must_be_whole_number", "enabled"], as_dict=True)
        if source == "site":
            if not cur:
                raise SeedError(f"UOM '{name}' phải có sẵn trên site (Q3) nhưng không tìm thấy")
            if not cur.enabled:
                raise SeedError(f"UOM '{name}' đang tắt trên site")
            rep.add("skipped", name, "có sẵn trên site, không sửa")
            continue
        if not cur:
            if ctx.apply:
                frappe.get_doc({"doctype": "UOM", "uom_name": name,
                                "must_be_whole_number": whole, "enabled": 1}).insert()
            ctx.plan("UOM", name)
            rep.add("created", name, f"must_be_whole_number={whole}")
        elif int(cur.must_be_whole_number or 0) != whole or not cur.enabled:
            if ctx.apply:
                doc = frappe.get_doc("UOM", name)
                doc.must_be_whole_number, doc.enabled = whole, 1
                doc.save()
            rep.add("updated", name, f"must_be_whole_number={whole}, enabled=1")
        else:
            rep.add("skipped", name)
