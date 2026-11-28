"""Bước 1: UOM. UOM có sẵn trên site (Litre, Millilitre, Gram, Kg) chỉ kiểm tra, không sửa (kể cả Symbol)."""
import frappe

from seed.common import SeedError, read_csv, to_int

TITLE = "UOM"


def load(ctx, rep, rows=None):
    rows = read_csv("uom.csv") if rows is None else rows
    has_symbol = frappe.get_meta("UOM").has_field("symbol")
    for r in rows:
        name, whole, source = r["uom"], to_int(r["must_be_whole_number"]), r["source"]
        symbol = (r.get("symbol") or "") if has_symbol else ""
        fields = ["must_be_whole_number", "enabled"] + (["symbol"] if has_symbol else [])
        cur = frappe.db.get_value("UOM", name, fields, as_dict=True)
        if source == "site":
            if not cur:
                raise SeedError(f"UOM '{name}' phải có sẵn trên site nhưng không tìm thấy")
            if not cur.enabled:
                raise SeedError(f"UOM '{name}' đang tắt trên site")
            rep.add("skipped", name, "có sẵn trên site, không sửa")
            continue
        want = {"must_be_whole_number": whole, "enabled": 1}
        if symbol:
            want["symbol"] = symbol
        if not cur:
            if ctx.apply:
                frappe.get_doc({"doctype": "UOM", "uom_name": name, **want}).insert()
            ctx.plan("UOM", name)
            rep.add("created", name, ", ".join(f"{k}={v}" for k, v in want.items()))
            continue
        diff = {k: v for k, v in want.items() if (cur.get(k) if isinstance(v, str) else int(cur.get(k) or 0)) != v}
        if not diff:
            rep.add("skipped", name)
            continue
        if ctx.apply:
            doc = frappe.get_doc("UOM", name)
            doc.update(diff)
            doc.save()
        rep.add("updated", name, ", ".join(f"{k}={v}" for k, v in diff.items()))
