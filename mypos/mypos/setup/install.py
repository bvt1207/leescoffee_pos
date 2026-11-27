"""Thiết lập app MYPOS khi cài mới / sau mỗi lần migrate (hooks.after_install, hooks.after_migrate).

Cài mới: `bench install-app` KHÔNG chạy patch (đánh dấu mọi patch là đã chạy), nên mọi thiết lập bắt buộc nằm ở đây.
DocType, Workspace, Sidebar, Desktop Icon đến từ file JSON của app; Custom Field / Property Setter / Role từ fixtures.
Quyền DocType của 3 role MYPOS: mypos/setup/roles.py (PERMS là nguồn chuẩn).
"""

from mypos.setup.roles import setup_roles_and_permissions


def after_install():
	# Cài mới: lỗi được ném ra để biết ngay site thiếu quyền.
	setup_roles_and_permissions(raise_errors=True)


def after_migrate():
	# Mỗi lần migrate: chỉ thêm phần thiếu; lỗi ghi Error Log, không làm migrate thất bại.
	setup_roles_and_permissions(raise_errors=False)
