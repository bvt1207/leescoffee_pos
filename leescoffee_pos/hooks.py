app_name = "leescoffee_pos"
app_title = "Leescoffee POS"
app_publisher = "BVTHACH"
app_description = "Thiet ke he thong POS cho Lees Coffee"
app_email = "bvtsk19@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "leescoffee_pos",
# 		"logo": "/assets/leescoffee_pos/logo.png",
# 		"title": "Leescoffee POS",
# 		"route": "/leescoffee_pos",
# 		"has_permission": "leescoffee_pos.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/leescoffee_pos/css/leescoffee_pos.css"
# app_include_js = "/assets/leescoffee_pos/js/leescoffee_pos.js"

# include js, css files in header of web template
# web_include_css = "/assets/leescoffee_pos/css/leescoffee_pos.css"
# web_include_js = "/assets/leescoffee_pos/js/leescoffee_pos.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "leescoffee_pos/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "leescoffee_pos/public/icons.svg"

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
# 	"methods": "leescoffee_pos.utils.jinja_methods",
# 	"filters": "leescoffee_pos.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "leescoffee_pos.install.before_install"
# after_install = "leescoffee_pos.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "leescoffee_pos.uninstall.before_uninstall"
# after_uninstall = "leescoffee_pos.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "leescoffee_pos.utils.before_app_install"
# after_app_install = "leescoffee_pos.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "leescoffee_pos.utils.before_app_uninstall"
# after_app_uninstall = "leescoffee_pos.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "leescoffee_pos.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "leescoffee_pos.notifications.get_notification_config"

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
		"on_submit": "leescoffee_pos.leescoffee_pos.doctype.pos_invoice_hooks.pos_invoice_hooks.on_submit",
		"before_save": "leescoffee_pos.leescoffee_pos.doctype.pos_invoice_hooks.pos_invoice_hooks.before_save",
		"on_update_after_submit": "leescoffee_pos.leescoffee_pos.doctype.pos_invoice_hooks.pos_invoice_hooks.on_update_after_submit",
		"on_cancel": "leescoffee_pos.leescoffee_pos.doctype.pos_invoice_hooks.pos_invoice_hooks.on_cancel",
	},
	# Leescoffee Buzzer: validate là native lifecycle method của Document →
	# Frappe tự gọi, không cần đăng ký lại trong doc_events.
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"leescoffee_pos.tasks.all"
# 	],
# 	"daily": [
# 		"leescoffee_pos.tasks.daily"
# 	],
# 	"hourly": [
# 		"leescoffee_pos.tasks.hourly"
# 	],
# 	"weekly": [
# 		"leescoffee_pos.tasks.weekly"
# 	],
# 	"monthly": [
# 		"leescoffee_pos.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "leescoffee_pos.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "leescoffee_pos.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "leescoffee_pos.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "leescoffee_pos.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Fixtures - DocTypes that should be exported
# -----------------------------------------------------------
# DocTypes created by this app that need to be included in fixtures
# so they are installed with the app on a fresh site.

fixtures = [
	{"dt": "DocType", "filters": [["name", "=", "Leescoffee POS Settings"]]},
	{"dt": "DocType", "filters": [["name", "=", "Leescoffee Buzzer"]]},
	{
		"dt": "Custom Field",
		"filters": [
			["dt", "=", "POS Invoice"],
		],
	},
	{
		"dt": "Custom Field",
		"filters": [
			["dt", "=", "Branch"],
		],
	},
]

# Request Events
# ----------------
# before_request = ["leescoffee_pos.utils.before_request"]
# after_request = ["leescoffee_pos.utils.after_request"]

# Job Events
# ----------
# before_job = ["leescoffee_pos.utils.before_job"]
# after_job = ["leescoffee_pos.utils.after_job"]

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
# 	"leescoffee_pos.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

