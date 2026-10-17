# Project Structure — Leescoffee POS

> Paths: `.claude/` và `leescoffee_pos/`

## .clanju/

```text
.claude/
├── CLAUDE.md                  # Project "bộ não" — giữ ngắn (see CLAUDE.md)
├── CLAUDE.local.md            # Ghi chú riêng, không push GitHub
├── memory.md                  # Index memory (auto-generated)
├── memory/
│   └── <memory files>
├── settings.json              # Permissions + hooks
├── settings.local.json        # Settings riêng, không push
├── agents/                    # Custom agents (currently unused)
├── rules/                     # Code standards + module-specific rules
│   ├── code-standards.md
│   ├── project-structure.md   # File này
│   └── session-management.md  # Ngữ cảnh phiên làm việc
│   └── leescoffee_pos/        # Logic per module
│       ├── sepay.md
│       ├── menu.md
│       └── branch_config.md
├── skills/                    # (currently unused)
└── docs/                      # Kế hoạch/features chưa làm (QR 3b/7b)
```

## leescoffee_pos/ (Frappe app)

```text
leescoffee_pos/
├── hooks.py                   # Hooks, doc_events, fixtures
├── modules.txt                # Module list ("Leescoffee Pos")
├── public/
├── templates/
└── leescoffee_pos/            # Package Python
    └── doctype/
        ├── leescoffee_pos_settings/
        │   ├── __init__.py, .json, .py
        ├── leescoffee_buzzer/
        │   ├── __init__.py, .json, .py
        ├── leescoffee_menu/
        │   ├── __init__.py, .json, .py
        ├── leescoffee_menu_item/
        │   ├── __init__.py, .json, .py
        ├── pos_invoice_hooks/
        │   ├── __init__.py, .py
        ├── sepay/
        │   ├── __init__.py, .py
        └── branch_config/
            ├── __init__.py, .py
```
