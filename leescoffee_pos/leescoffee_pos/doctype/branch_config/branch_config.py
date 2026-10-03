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
        dict: Dictionary containing all branch config fields with fallback to Settings.
    """
    if not branch_name:
        branch_name = get_default_branch()

    if not branch_name:
        return {}

    # Get branch document
    branch = frappe.get_doc("Branch", branch_name)
    settings = frappe.get_single("Leescoffee POS Settings")

    config = {}

    # SePay configuration with fallback
    config["sepay_enabled"] = branch.sepay_enabled if branch.sepay_enabled is not None else settings.sepay_enabled or 0
    config["sepay_merchant_code"] = branch.sepay_merchant_code or settings.sepay_merchant_code or ""
    config["sepay_api_key"] = branch.sepay_api_key or settings.sepay_api_key or ""
    config["sepay_secret_key"] = branch.sepay_secret_key or settings.sepay_secret_key or ""
    config["sepay_env"] = branch.sepay_env or settings.sepay_env or "sandbox"
    config["sepay_callback_url"] = branch.sepay_callback_url or settings.sepay_callback_url or ""

    # Branding with fallback
    config["brand_name"] = branch.brand_name or settings.brand_name or ""
    config["brand_logo"] = branch.brand_logo or settings.brand_logo or ""
    config["brand_banner"] = branch.brand_banner or settings.brand_banner or ""
    config["brand_phone"] = branch.brand_phone or settings.brand_phone or ""
    config["brand_address"] = branch.brand_address or settings.brand_address or ""

    return config


def get_sepay_config(branch_name=None):
    """Get SePay configuration for a branch with fallback to Settings.

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
    settings = frappe.get_single("Leescoffee POS Settings")

    return {
        "enabled": branch.sepay_enabled if branch.sepay_enabled is not None else settings.sepay_enabled or 0,
        "merchant_code": branch.sepay_merchant_code or settings.sepay_merchant_code or "",
        "api_key": branch.sepay_api_key or settings.sepay_api_key or "",
        "secret_key": branch.sepay_secret_key or settings.sepay_secret_key or "",
        "env": branch.sepay_env or settings.sepay_env or "sandbox",
        "callback_url": branch.sepay_callback_url or settings.sepay_callback_url or "",
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
    settings = frappe.get_single("Leescoffee POS Settings")

    enabled = branch.sepay_enabled if branch.sepay_enabled is not None else settings.sepay_enabled or 0
    return 1 if enabled else 0