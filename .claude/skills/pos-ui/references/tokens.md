# Design System Tokens — Leescoffee POS

> Nguồn: `.claude/docs/pos-ui-design.md` §1 (Design System Overview). Tất cả giá trị dưới dạng CSS biến `--pos-*` trong `global.css`.  
> **Màu thương hiệu chỉ là giá trị mặc định** trong tokens này — khi white-label cho khách khác, chỉ cần đổi `--pos-primary` là toàn bộ giao diện tự thay đổi. Không hardcode tên thương hiệu nào vào tên token.

## 1. Màu sắc (Color Tokens)

Màu đỏ thương hiệu `#C8102E` được định nghĩa **một lần duy nhất** tại `--pos-primary` để dễ đối chiếu lại bằng eyedropper sau.

### 1.1 Màu chính (brand)
```css
--pos-primary: #C8102E;         /* đỏ thương hiệu - nút chính / điểm nhấn */
--pos-primary-contrast: #FFFFFF; /* chữ trên nút đỏ */
--pos-primary-hover: #A80D26;   /* hover nút chính */
--pos-primary-active: #8B0A1F;  /* active / pressed nút chính */
--pos-primary-disabled: #F1C2C9; /* disabled nút chính (chữ #9E8E92) */
```

### 1.2 Màu nền & bề mặt
```css
--pos-bg: #FFFFFF;              /* nền lớn */
--pos-surface: #F5F5F7;         /* panel, card - xám rất nhạt */
--pos-surface-alt: #ECECEF;     /* panel ngầm, input background */
```

### 1.3 Màu chữ & viền
```css
--pos-text: #2A2520;            /* chữ chính - nâu đen */
--pos-text-muted: #6B6560;      /* chữ phụ - xám nâu nhạt */
--pos-border: #E3E1E0;          /* viền nhẹ */
```

### 1.4 Màu trạng thái
```css
--pos-success: #2E7D4F;   /* xanh lá - thành công */
--pos-warning: #C88A2E;   /* cam - chờ xử lý */
--pos-error: #C8102E;     /* đỏ - lỗi/hủy (dùng chung brand red) */
```

### 1.5 Kiểm tra tương đối (WCAG AA)
- `rgba(255,255,255)` trên `#C8102E` → **5.81:1** ✓ đạt AA cho chữ thường (≥4.5:1)
- `#2A2520` trên `#FFFFFF` → **15.08:1** ✓
- `#FFFFFF` trên `#2E7D4F` → ~6.5:1 ✓

> **Lưu ý:** Nếu eyedropper sau cho màu đỏ khác, chỉ cần đổi giá trị hex tại `--pos-primary` (và tái suy `--pos-primary-hover`/`--pos-primary-active`/`--pos-primary-disabled` từ đó). Các component chỉ được tham chiếu `--pos-primary-*`, không được viết literal màu.

## 2. Khoảng cách (Spacing Token)

```css
--pos-spacing-xs: 4px;
--pos-spacing-sm: 8px;
--pos-spacing-md: 12px;
--pos-spacing-lg: 16px;
--pos-spacing-xl: 20px;
--pos-spacing-xxl: 24px;
```

## 3. Bán kính bo góc (Radius Token)

```css
--pos-radius-sm: 6px;
--pos-radius-md: 10px;
--pos-radius-lg: 12px;
--pos-radius-full: 999px;  /* button, chip */
```

## 4. Đổ bóng (Elevation / Shadow)

```css
--pos-shadow-sm: 0 1px 3px rgba(60, 45, 30, 0.05);
--pos-shadow-md: 0 2px 10px rgba(60, 45, 30, 0.08);
--pos-shadow-lg: 0 4px 20px rgba(60, 45, 30, 0.12);
```

## Quy tắc sử dụng

- Không định nghĩa màu mới literals trong component; luôn dùng biến `--pos-*`.
- Xem lại `global.css` khi cần thêm token mới.
