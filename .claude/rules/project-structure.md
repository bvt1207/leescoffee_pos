# Project Structure — Leescoffee POS

> Paths: `.claude/` và `leescoffee_pos/`. Cây đầy đủ, đã đối chiếu đĩa (2026-10-27): CLAUDE.md §10.

## .claude/

```text
.claude/
├── CLAUDE.md                  # Project "bộ não" (see CLAUDE.md)
├── CLAUDE.local.md            # Ghi chú riêng
├── memory.md                  # Index memory → file nằm ở PROJECTPOS/memory/
├── settings.json              # Permissions + hooks
├── settings.local.json        # Settings riêng, không push
├── agents/                    # (currently unused)
├── rules/
│   ├── code-standards.md
│   ├── project-structure.md   # File này
│   ├── session-management.md
│   └── leescoffee_pos/        # Logic per module
│       ├── menu.md
│       ├── pos_invoice_hooks.md
│       ├── sepay.md
│       └── workspace.md
├── skills/
│   ├── frontend-design/
│   └── pos-ui/                # SKILL.md, layout.md, states.md, references/, examples/
└── docs/
    ├── task_handoff.md        # Bàn giao giữa các phiên
    └── reference/             # Ảnh tham khảo UI
```

## leescoffee_pos/ (package Python của app — không có pyproject.toml trong repo này)

```text
leescoffee_pos/
├── hooks.py                   # doc_events, website_route_rules, fixtures
├── modules.txt                # "Leescoffee POS" (lệch tên module, xem CLAUDE.md §5)
├── fixtures/custom_field.json
├── desktop_icon/, workspace_sidebar/
├── public/                    # images/logo.svg; pos/ = output build Vite
├── www/pos.html, pos.py       # route /pos (+ /pos/* qua website_route_rules)
├── pos/                       # React + Vite + TSX (src/pages, components, store, lib, styles)
└── leescoffee_pos/            # module "Leescoffee Pos"
    ├── api/pos_api.py         # whitelisted API cho frontend POS
    ├── workspace/leescoffee_pos/leescoffee_pos.json
    └── doctype/
        ├── leescoffee_pos_settings/   # __init__.py, .json, .py
        ├── leescoffee_buzzer/         # __init__.py, .json, .py
        ├── leescoffee_menu/           # __init__.py, .json, .py
        ├── leescoffee_menu_item/      # __init__.py, .json, .py
        ├── pos_invoice_hooks/         # __init__.py, .py
        ├── sepay/                     # __init__.py, .py
        └── branch_config/             # __init__.py, .py
```
