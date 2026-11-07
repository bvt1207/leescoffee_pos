---
name: branding-fallback-branch-vs-settings
description: Branch là nguồn cấu hình duy nhất (branding + SePay + company); không còn fallback Leescoffee POS Settings
metadata:
  type: feedback
---

**Trạng thái (2026-11-08):** `branch_config.get_brand_info()`, `get_branch_config()`,
`get_sepay_config()` chỉ đọc từ `Branch`. Chi nhánh lấy từ `POS Profile.branch`, hoặc
`resolve_pos_profile_name()` khi không có profile. `Leescoffee POS Settings` không còn được
code đọc; DocType đã xóa (patch `v1_remove_pos_settings`). Chi tiết: `.claude/rules/leescoffee_pos/branch.md`.

**Why:** Van quyết định gom cấu hình về Branch để triển khai nhiều doanh nghiệp/chi nhánh
(white-label); Settings thiếu field `brand_*` từng gây `AttributeError: brand_banner`.

**How to apply:**
- Cần branding → `get_brand_info()` (qua `get_pos_config`), không đọc Settings.
- Không thêm fallback mới sang Settings; field Branch rỗng thì trả `""`.
- Không hardcode giá trị branding nào vào code/template/asset.
