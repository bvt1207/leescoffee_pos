app_name = "mypos"
app_title = "MYPOS"
app_publisher = "BVTHACH"
app_description = "POS for coffee shop chain"
app_email = "bvtsk19@gmail.com"
app_license = "mit"

# Apps
# ------------------

# Branch, POS Invoice, POS Profile... đều thuộc ERPNext (Branch: erpnext/setup/doctype/branch). Không cần HRMS.
required_apps = ["erpnext"]

# Each item in the list will be shown as an app in the apps page
# Ô MYPOS trên màn Apps của Desk (chế độ mặc định "Apps"; không dùng lưới Desktop Icon đang bị Frappe loại bỏ).
# KHÔNG khai "route": Frappe 16.61 chỉ có route tĩnh; bỏ trống thì client đi theo "landing ladder"
# (`sidebar.js::app_landing_route`): app không có Dock -> mục đầu tiên của Sidebar "MYPOS" ĐÃ LỌC theo quyền user
# Sidebar xếp Admin, Manager, Cashier, Kitchen -> System Manager / Administrator vào MYPOS Admin, POS MANAGER vào MYPOS Manager,
# POS CASHIER vào MYPOS Cashier, POS KITCHEN vào MYPOS Kitchen (docs/rules/workspace.md).
add_to_apps_screen = [
	{
		"name": "mypos",
		"logo": "/assets/mypos/images/logo.svg",
		"title": "MYPOS",
		"has_permission": "mypos.permissions.has_app_permission",
	}
]

# The dock, the rail down the left of the desk, is a document rather than a hook. Author it in
# Manage Dock on a developer-mode site and press Export to App, and it is written to
# `mypos/dock/mypos/mypos.json` for git to carry. An app that ships none has no
# rail: its sidebar gets a switcher in the header instead.
#
# A companion app, one that extends a host app rather than standing on its own, says so with
# `mount_on` on that same record, and its entries are appended to the host's rail. Mounting keeps
# the companion off the apps screen, so it takes precedence over any add_to_apps_screen above.

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/mypos/css/mypos.css"
# app_include_js = "/assets/mypos/js/mypos.js"

# include js, css files in header of web template
# web_include_css = "/assets/mypos/css/mypos.css"
# web_include_js = "/assets/mypos/js/mypos.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "mypos/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# POS Opening Entry: tự điền Cashier = người đăng nhập, khóa với người không phải quản lý (server vẫn chặn).
# POS Invoice: nút "Hủy đơn" (Draft) và "Xử lý đơn" (đã thu tiền, Chưa làm / Đã làm) cho quản lý.
# POS Profile: Khách vãng lai chỉ cho chọn Customer đang bật.
doctype_js = {
	"POS Opening Entry": "public/js/pos_opening_entry.js",
	"POS Invoice": "public/js/pos_invoice.js",
	"POS Profile": "public/js/pos_profile.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_kanban_js = {"doctype" : "public/js/doctype_kanban.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "mypos/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "mypos.utils.jinja_methods",
# 	"filters": "mypos.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "mypos.install.before_install"
# Cài mới: install-app không chạy patch -> tạo Role POS + quyền ở đây (idempotent, mypos/setup/).
after_install = "mypos.setup.install.after_install"
# Mỗi lần migrate: bổ sung role / quyền còn thiếu theo PERMS (chỉ thêm, lỗi không làm migrate thất bại).
after_migrate = "mypos.setup.install.after_migrate"

# Uninstallation
# ------------

# before_uninstall = "mypos.uninstall.before_uninstall"
# after_uninstall = "mypos.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "mypos.utils.before_app_install"
# after_app_install = "mypos.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "mypos.utils.before_app_uninstall"
# after_app_uninstall = "mypos.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "mypos.build.after_build"

# To hook into the build process of other apps
# The list of apps being built is passed as an argument

# after_app_build = "mypos.build.after_app_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "mypos.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["mypos.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"POS Invoice": {
		# CTKM theo tổng qty mỗi mã: áp lại sau khi ERPNext chọn Pricing Rule theo từng dòng (ERPNext 16.61, options.md §7).
		"validate": "mypos.mypos.doctype.pos_invoice_hooks.pos_invoice_hooks.validate",
		"before_submit": "mypos.mypos.doctype.pos_invoice_hooks.pos_invoice_hooks.before_submit",
		"on_submit": "mypos.mypos.doctype.pos_invoice_hooks.pos_invoice_hooks.on_submit",
		"before_save": "mypos.mypos.doctype.pos_invoice_hooks.pos_invoice_hooks.before_save",
		"on_update_after_submit": "mypos.mypos.doctype.pos_invoice_hooks.pos_invoice_hooks.on_update_after_submit",
		"on_cancel": "mypos.mypos.doctype.pos_invoice_hooks.pos_invoice_hooks.on_cancel",
		# Phiên bản thay đổi theo POS Profile (Redis, sau commit) -> màn POS chỉ tải lại khi đổi (change_feed.py).
		"on_change": "mypos.mypos.doctype.pos_invoice_hooks.change_feed.on_doc_change",
	},
	# Mở / đóng ca: chỉ ca của chính mình, MANAGER thao tác thay (pos_shift_hooks.py).
	"POS Opening Entry": {
		"before_validate": "mypos.mypos.doctype.pos_shift_hooks.pos_shift_hooks.opening_before_validate",
		"before_submit": "mypos.mypos.doctype.pos_shift_hooks.pos_shift_hooks.opening_before_submit",
		"on_submit": "mypos.mypos.doctype.pos_shift_hooks.pos_shift_hooks.opening_on_submit",
		"on_change": "mypos.mypos.doctype.pos_invoice_hooks.change_feed.on_doc_change",
	},
	"POS Closing Entry": {
		"before_validate": "mypos.mypos.doctype.pos_shift_hooks.pos_shift_hooks.closing_before_validate",
		"before_submit": "mypos.mypos.doctype.pos_shift_hooks.pos_shift_hooks.closing_before_submit",
		"on_submit": "mypos.mypos.doctype.pos_shift_hooks.pos_shift_hooks.closing_on_submit",
		"on_change": "mypos.mypos.doctype.pos_invoice_hooks.change_feed.on_doc_change",
	},
	# Khách vãng lai, Branch bắt buộc, 1 profile đang bật / Branch (pos_profile_hooks.py).
	"POS Profile": {
		"validate": "mypos.mypos.doctype.pos_profile_hooks.pos_profile_hooks.validate",
		# Cache POS Profile của user (get_pos_changes) -> xóa khi lưu / xóa profile.
		"on_update": "mypos.mypos.doctype.pos_invoice_hooks.change_feed.clear_profile_cache",
		"on_trash": "mypos.mypos.doctype.pos_invoice_hooks.change_feed.clear_profile_cache",
	},
	# MYPOS Buzzer: validate là native lifecycle method của Document -> Frappe tự gọi, không đăng ký ở đây.
}

# Website Route Rules
# -------------------
# /pos/* (orders, kitchen, customer, status) dùng chung www/pos.html, định tuyến còn lại do React Router.
# "/pos" (không hậu tố) Frappe tự resolve tới www/pos.html.
website_route_rules = [
	{"from_route": "/pos/<path:app_path>", "to_route": "pos"},
	# Web đặt món QR cho khách: /order/<token> -> www/mypos_order.html (React app riêng, không cần đăng nhập).
	# KHÔNG đặt tên trang "order": ERPNext đã có templates/pages/order (/orders/<name>).
	{"from_route": "/order/<path:app_path>", "to_route": "mypos_order"},
]

# Scheduled Tasks
# ---------------

# Tự hủy (chuyển Cancelled, lưu lý do) đơn Draft quá hạn: QR quá hạn thanh toán + đệm webhook, Draft kênh khác
# quá 120 phút (mốc ở doctype/pos_invoice_hooks/order_cancel.py).
scheduler_events = {
	"cron": {
		"*/5 * * * *": [
			"mypos.mypos.doctype.pos_invoice_hooks.order_cancel.auto_cancel_stale_drafts",
		],
	},
}

# scheduler_events = {
# 	"all": [
# 		"mypos.tasks.all"
# 	],
# 	"daily": [
# 		"mypos.tasks.daily"
# 	],
# 	"hourly": [
# 		"mypos.tasks.hourly"
# 	],
# 	"weekly": [
# 		"mypos.tasks.weekly"
# 	],
# 	"monthly": [
# 		"mypos.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "mypos.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "mypos.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "mypos.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "mypos.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Fixtures
# --------
# Custom Field / Property Setter trên DocType chuẩn (module MYPOS) và 3 Role.
# Quyền (Custom DocPerm) KHÔNG dùng fixture: đặt qua mypos/setup/roles.py (PERMS).
fixtures = [
	{"dt": "Custom Field", "filters": [["dt", "=", "POS Invoice"]]},
	{"dt": "Custom Field", "filters": [["dt", "=", "POS Profile"]]},
	{"dt": "Custom Field", "filters": [["dt", "=", "Branch"]]},
	{"dt": "Custom Field", "filters": [["dt", "=", "Customer"], ["fieldname", "=", "mobile_number"]]},
	{"dt": "Custom Field", "filters": [["dt", "=", "POS Invoice Item"]]},
	# Bộ lọc chuẩn POS Profile trên danh sách POS Invoice, CHỈ đúng 1 dòng.
	{"dt": "Property Setter", "filters": [["name", "in", ["POS Invoice-pos_profile-in_standard_filter"]]]},
	{"dt": "Role", "filters": [["name", "in", ["POS CASHIER", "POS KITCHEN", "POS MANAGER"]]]},
]

# Request Events
# ----------------
# before_request = ["mypos.utils.before_request"]
# after_request = ["mypos.utils.after_request"]

# Job Events
# ----------
# before_job = ["mypos.utils.before_job"]
# after_job = ["mypos.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"mypos.auth.validate"
# ]

# on_social_login = "mypos.auth.on_social_login"

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

