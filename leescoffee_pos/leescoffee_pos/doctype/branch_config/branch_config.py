import frappe
from frappe import _


def get_default_branch():
    """Get the default branch from Leescoffee POS Settings."""
    settings = frappe.get_single("Leescoffee POS Settings")
    return settings.default_branch or ""


def get_branch_config(branch_name=None):
    """Get all configuration fields for a specific branch.

    Args:
        branch_name (str): Name of the Branch. If None, uses default branch.

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

    # SePay configuration - no fallback to Settings
    config["sepay_enabled"] = branch.sepay_enabled if branch.sepay_enabled is not None else 0
    config["sepay_merchant_code"] = branch.sepay_merchant_code or ""
    config["sepay_api_key"] = branch.sepay_api_key or ""
    config["sepay_secret_key"] = branch.sepay_secret_key or ""
    config["sepay_env"] = branch.sepay_env or "sandbox"
    config["sepay_callback_url"] = branch.sepay_callback_url or ""

    # Branch-specific SePay VA and bank for VietQR
    config["sepay_va_account"] = branch.sepay_va_account or ""
    config["sepay_bank_code"] = branch.sepay_bank_code or ""

    # Branding - keep fallback to Settings
    config["brand_name"] = branch.brand_name or ""
    config["brand_logo"] = branch.brand_logo or ""
    config["brand_banner"] = branch.brand_banner or ""
    config["brand_phone"] = branch.brand_phone or ""
    config["brand_address"] = branch.brand_address or ""

    return config


def get_sepay_config(branch_name=None):
    """Get SePay configuration for a branch.

    Args:
        branch_name (str): Name of the Branch. If None, uses default branch.

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
        "merchant_code": branch.sepay_merchant_code or "",
        "api_key": branch.sepay_api_key or "",
        "secret_key": branch.sepay_secret_key or "",
        "env": branch.sepay_env or "sandbox",
        "callback_url": branch.sepay_callback_url or "",
        "va_account": branch.sepay_va_account or "",
        "bank_code": branch.sepay_bank_code or "",
    }


def get_brand_info(branch_name=None):
    """Get branding information for a branch with fallback to Settings.

    Args:
        branch_name (str): Name of the Branch. If None, uses default branch.

    Returns:
        dict: Branding information dictionary.
    """
    if not branch_name:
        branch_name = get_default_branch()

    if not branch_name:
        return {}

    branch = frappe.get_doc("Branch", branch_name)
    settings = frappe.get_single("Leescoffee POS Settings")

    return {
        "name": branch.brand_name or settings.brand_name or "",
        "logo": branch.brand_logo or settings.brand_logo or "",
        "banner": branch.brand_banner or settings.brand_banner or "",
        "phone": branch.brand_phone or settings.brand_phone or "",
        "address": branch.brand_address or settings.brand_address or "",
    }


def get_sepay_enabled(branch_name=None):
    """Check if SePay is enabled for a branch.

    Args:
        branch_name (str): Name of the Branch. If None, uses default branch.

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
    """
    invoice = frappe.get_doc("POS Invoice", invoice_name)

    # Get branch from invoice (via POS Profile or default)
    branch_name = None
    if invoice.pos_profile:
        pos_profile = frappe.get_doc("POS Profile", invoice.pos_profile)
        branch_name = pos_profile.branch

    if not branch_name:
        branch_name = get_default_branch()

    if not branch_name:
        return {"va_account": "", "bank_code": ""}

    branch = frappe.get_doc("Branch", branch_name)
    settings = frappe.get_single("Leescoffee POS Settings")

    return {
        "va_account": branch.sepay_va_account or settings.sepay_va_account or "",
        "bank_code": branch.sepay_bank_code or settings.sepay_bank_code or "",
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