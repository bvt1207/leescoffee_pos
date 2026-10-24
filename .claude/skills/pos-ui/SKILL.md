---
name: pos-ui
description: Hướng dẫn thiết kế UI/UX cho frontend POS (React/TSX): design system tokens, bố cục, component, trạng thái, quy tắc tránh hardcode branding Lee's Coffee.
---

# Skill — UI/UX Design cho Leescoffee POS Frontend

> **Khi sử dụng:** Lúc tạo hoặc sửa component React/TSX của giao diện POS (`POS.tsx`, `Orders.tsx`, `Table.tsx` và các component con). Hướng dẫn thiết kế giao diện POS chuyên nghiệp, hiện đại, không hardcode branding Lee's Coffee.

## Cấu trúc skill

- [`references/tokens.md`](references/tokens.md) — màu sắc, khoảng cách, bán kính, độ nổi (CSS biến `--pos-*`)
- [`layout.md`](layout.md) — bố cục trang, routing, phân rẽ component, bản đồ API, chuẩn CSS và touch
- [`states.md`](states.md) — trạng thái component, zustand cart, mẫu component, tích hợp API, quy ước đặt tên, checklist commit
- [`examples/`](examples/) — component mẫu thực tế: AppHeader.tsx, MenuGrid.tsx, SizeModal.tsx, CartPanel.tsx, POS.tsx, CustomerPicker.tsx, Orders.tsx, Kitchen.tsx, global.css

## Quy tắc cốt lõi

- **Không hardcode** tên "Lee's Coffee", logo, màu thương hiệu, banner trong JSX hay CSS — luôn đọc từ API (`get_pos_config`) hoặc dùng biến CSS `--pos-*`.
- Mục chạm tối thiểu 44×44px.
- Không dùng CSS framework bên ngoài (không MUI, không Tailwind).
- Tất cả style qua class trong `global.css`, không inline style.
- **Token và bố cục của dự án (skill `pos-ui`) ưu tiên hơn `frontend-design`** khi có mâu thuẫn về màu sắc hoặc layout.
