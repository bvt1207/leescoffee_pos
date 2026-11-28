"""Dùng chung cho các loader: ngữ cảnh (Company đọc từ site), báo cáo, đọc CSV sạch."""
import csv
from pathlib import Path

import frappe

SEED_DIR = Path(__file__).resolve().parent
CLEAN_DIR = SEED_DIR / "clean"
MODES = ("dry-run", "apply")


class SeedError(Exception):
    """Lỗi dữ liệu / cấu hình: dừng bước hiện tại, không in traceback."""


class Report:
    ACTIONS = ("created", "updated", "skipped", "error")

    def __init__(self, step, title, mode):
        self.step, self.title, self.mode = step, title, mode
        self.counts = dict.fromkeys(self.ACTIONS, 0)

    def add(self, action, key, detail=""):
        self.counts[action] += 1
        label = action if self.mode == "apply" or action in ("skipped", "error") else f"sẽ {action}"
        print(f"  [{label}] {key}" + (f" — {detail}" if detail else ""))

    def warn(self, msg):
        print(f"  [cảnh báo] {msg}")

    def line(self):
        c = self.counts
        return (f"{self.step:<18} created={c['created']:<3} updated={c['updated']:<3} "
                f"skipped={c['skipped']:<3} error={c['error']}")


class Ctx:
    """mode: 'dry-run' (mặc định, không ghi) hoặc 'apply'."""

    def __init__(self, mode="dry-run", company=None):
        if mode not in MODES:
            raise SeedError(f"mode phải là {MODES}, nhận '{mode}'")
        self.mode = mode
        self.apply = mode == "apply"
        self.company = resolve_company(company)
        self.abbr, self.currency, self.cost_center = frappe.db.get_value(
            "Company", self.company, ["abbr", "default_currency", "cost_center"])
        # Bản ghi "sẽ tạo" ở dry-run, để bước sau kiểm tra link không báo lỗi giả.
        self.planned = set()

    def plan(self, doctype, name):
        self.planned.add((doctype, name))

    def exists(self, doctype, name):
        return (doctype, name) in self.planned or bool(frappe.db.exists(doctype, name))

    def in_db(self, doctype, name):
        return bool(frappe.db.exists(doctype, name))

    def wh(self, warehouse_name):
        return f"{warehouse_name} - {self.abbr}"


def resolve_company(company=None):
    if company:
        if not frappe.db.exists("Company", company):
            raise SeedError(f"Không có Company '{company}' trên site")
        return company
    names = frappe.get_all("Company", pluck="name")
    if len(names) != 1:
        raise SeedError(f"Site có {len(names)} Company ({', '.join(names)}); truyền tham số company=...")
    return names[0]


def read_csv(fname):
    path = CLEAN_DIR / fname
    if not path.exists():
        raise SeedError(f"Thiếu {path}. Chạy tools/seed/clean.py trước.")
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def to_int(v):
    return int(float(v)) if str(v or "").strip() else 0


def to_float(v):
    return float(v) if str(v or "").strip() else 0.0


def require(ctx, doctype, name, who):
    if not name or not ctx.exists(doctype, name):
        raise SeedError(f"{who}: {doctype} '{name}' chưa có trên site (và không nằm trong kế hoạch tạo)")
