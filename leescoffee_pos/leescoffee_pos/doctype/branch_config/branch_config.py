import frappe
from frappe import _


def resolve_pos_profile_name():
    """Xác định POS Profile khi nơi gọi không truyền chi nhánh.

    Thứ tự (2026-11-25):
      1. User nằm trong "Applicable for Users" của ít nhất một POS Profile ĐANG BẬT -> lấy profile đầu tiên
         (`default = 1` trước, rồi tên A→Z). Profile đó thiếu branch -> throw, KHÔNG rơi sang profile khác.
      2. User không thuộc profile đang bật nào (vd. Administrator / System Manager): đúng MỘT POS Profile đang bật
         có gán branch.
      3. Còn lại: frappe.throw (không đoán bừa).

    Returns:
        str: tên POS Profile.
    """
    user_rows = frappe.get_all(
        "POS Profile User",
        filters={"user": frappe.session.user, "parenttype": "POS Profile"},
        fields=["parent", "default"],
    )
    if user_rows:
        enabled = {
            p.name: p.branch
            for p in frappe.get_all(
                "POS Profile",
                filters={"name": ["in", list({r.parent for r in user_rows})], "disabled": 0},
                fields=["name", "branch"],
            )
        }
        # Frappe v16 chặn backtick trong order_by -> sắp xếp bằng Python: default = 1 trước, rồi tên A→Z.
        rows = sorted(
            (r for r in user_rows if r.parent in enabled),
            key=lambda r: (-(r.get("default") or 0), r.parent),
        )
        if rows:
            chosen = rows[0].parent
            if not enabled[chosen]:
                frappe.throw(
                    _(
                        "POS Profile {0} của bạn chưa được gán chi nhánh (Branch). "
                        "Nhờ quản lý chọn Branch cho profile này."
                    ).format(chosen),
                    title=_("Thiếu chi nhánh"),
                )
            return chosen

    profiles = frappe.get_all(
        "POS Profile",
        filters={"disabled": 0, "branch": ["is", "set"]},
        pluck="name",
    )
    if len(profiles) == 1:
        return profiles[0]

    if not profiles:
        frappe.throw(
            _("Không xác định được chi nhánh: chưa có POS Profile nào đang bật và được gán Branch.")
        )
    frappe.throw(
        _(
            "Không xác định được chi nhánh: có {0} POS Profile đang bật ({1}). "
            "Hãy gán user {2} vào bảng Applicable for Users của đúng POS Profile."
        ).format(len(profiles), ", ".join(profiles), frappe.session.user)
    )


def get_default_branch():
    """Chi nhánh mặc định, lấy từ POS Profile (không còn Leescoffee POS Settings).

    Giữ tên hàm cũ để không vỡ nơi gọi. Ném lỗi nếu không xác định được.
    """
    profile_name = resolve_pos_profile_name()
    return frappe.db.get_value("POS Profile", profile_name, "branch")


def get_branch_config(branch_name=None):
    """Get all configuration fields for a specific branch.

    Args:
        branch_name (str): Name of the Branch. If None, lấy branch từ POS Profile (get_default_branch).

    Returns:
        dict: Dictionary containing all branch config fields.
    """
    if not branch_name:
        branch_name = get_default_branch()

    if not branch_name:
        return {}

    # Get branch document
    branch = frappe.get_doc("Branch", branch_name)

    config = {}

    # Branch là nguồn cấu hình duy nhất (SePay + thương hiệu + company)
    config["company"] = branch.get("company") or ""

    # SePay configuration
    config["sepay_enabled"] = branch.sepay_enabled if branch.sepay_enabled is not None else 0
    config["sepay_api_key"] = branch.sepay_api_key or ""

    # Branch-specific SePay VA and bank for VietQR
    config["sepay_va_account"] = branch.sepay_va_account or ""
    config["sepay_bank_code"] = branch.sepay_bank_code or ""

    # Branding - chỉ đọc từ Branch
    config["brand_name"] = branch.get("brand_name") or ""
    config["brand_logo"] = branch.get("brand_logo") or ""
    config["brand_phone"] = branch.get("brand_phone") or ""
    config["brand_address"] = branch.get("brand_address") or ""

    return config


def get_sepay_config(branch_name=None):
    """Get SePay configuration for a branch.

    Args:
        branch_name (str): Name of the Branch. If None, lấy branch từ POS Profile (get_default_branch).

    Returns:
        dict: SePay configuration dictionary.
    """
    if not branch_name:
        branch_name = get_default_branch()

    if not branch_name:
        return {}

    branch = frappe.get_doc("Branch", branch_name)

    return {
        "enabled": branch.sepay_enabled if branch.sepay_enabled is not None else 0,
        "api_key": branch.sepay_api_key or "",
        "va_account": branch.sepay_va_account or "",
        "bank_code": branch.sepay_bank_code or "",
    }


def get_brand_info(branch_name=None):
    """Get branding information for a branch.

    Chỉ đọc từ Branch.

    Args:
        branch_name (str): Name of the Branch. If None, lấy branch từ POS Profile (get_default_branch).

    Returns:
        dict: Branding information dictionary.
    """
    if not branch_name:
        branch_name = get_default_branch()

    if not branch_name:
        return {}

    branch = frappe.get_doc("Branch", branch_name)

    return {
        "name": branch.get("brand_name") or "",
        "logo": branch.get("brand_logo") or "",
        "phone": branch.get("brand_phone") or "",
        "address": branch.get("brand_address") or "",
    }


def get_sepay_enabled(branch_name=None):
    """Check if SePay is enabled for a branch.

    Args:
        branch_name (str): Name of the Branch. If None, lấy branch từ POS Profile (get_default_branch).

    Returns:
        int: 1 if enabled, 0 if disabled.
    """
    if not branch_name:
        branch_name = get_default_branch()

    if not branch_name:
        return 0

    branch = frappe.get_doc("Branch", branch_name)

    enabled = branch.sepay_enabled if branch.sepay_enabled is not None else 0
    return 1 if enabled else 0


def get_va_bank_config(invoice_name):
    """Get VietQR VA and bank config for a specific invoice.

    Args:
        invoice_name (str): Name of the POS Invoice.

    Returns:
        dict: VietQR config with va_account and bank_code.

    Raises:
        frappe.ValidationError: If POS Profile branch is not set or SePay is not configured.
    """
    invoice = frappe.get_doc("POS Invoice", invoice_name)

    # Get branch from invoice (via POS Profile)
    branch_name = None
    if invoice.pos_profile:
        pos_profile = frappe.get_doc("POS Profile", invoice.pos_profile)
        branch_name = pos_profile.branch

    # If POS Profile doesn't have branch set, throw clear error
    if not branch_name:
        frappe.throw(_("POS Profile {0} chưa được gán chi nhánh. Vui lòng cấu hình chi nhánh trong tab Accounting.").format(invoice.pos_profile))

    # Get branch document
    branch = frappe.get_doc("Branch", branch_name)

    # Check if SePay is enabled for this branch
    if not branch.sepay_enabled:
        frappe.throw(_("SePay chưa được kích hoạt cho chi nhánh {0}. Vui lòng bật SePay trong cấu hình chi nhánh.").format(branch_name))

    # Check if VA account and bank code are configured
    if not branch.sepay_va_account:
        frappe.throw(_("Tài khoản Virtual Account chưa được cấu hình cho chi nhánh {0}.").format(branch_name))

    if not branch.sepay_bank_code:
        frappe.throw(_("Mã ngân hàng chưa được cấu hình cho chi nhánh {0}.").format(branch_name))

    return {
        "va_account": branch.sepay_va_account,
        "bank_code": branch.sepay_bank_code,
        "branch": branch_name
    }


def get_sepay_qr_url(va_account, bank_code, amount, payment_code):
    """Generate VietQR URL from VA account and bank code.

    Args:
        va_account (str): Virtual account number
        bank_code (str): Bank code
        amount (float): Amount to pay
        payment_code (str): Unique payment reference

    Returns:
        str: VietQR URL
    """
    if not va_account or not bank_code:
        return ""

    # Ensure amount is in proper format (VND)
    amount_int = int(float(amount))

    return f"https://vietqr.app/img?acc={va_account}&bank={bank_code}&amount={amount_int}&des={payment_code}"