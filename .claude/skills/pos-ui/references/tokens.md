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

### 1.5 Màu phụ dẫn xuất (đã có trong `global.css`)
Chuyển từ màu viết cứng sang token ở bước refactor d1, giữ nguyên giá trị cũ.
```css
--pos-error-soft: #fbe6e3;      /* nền nhạt lỗi/hủy: alert lỗi, hover nút danger, hover Đăng xuất */
--pos-error-border: #f0c4be;    /* viền lỗi/hủy: alert lỗi, nút danger */
--pos-warning-soft: #f3e6cf;    /* nền nhạt trạng thái chờ: .pos-status__badge, .pos-tag--warn */
--pos-note-bg: #fff4d6;         /* nền ghi chú đơn ở màn Pha chế (.pos-kcard__note) */
--pos-success-soft: #e8f4ec;    /* nền thẻ rung sẵn sàng (.pos-buzzer) */
--pos-on-solid: #fff;           /* chữ/nền trắng trên nền đậm (nút success/danger-solid, toast, ảnh QR) */
--pos-overlay: rgba(35, 27, 20, 0.55);          /* lớp phủ sau modal */
--pos-chip-on-media: rgba(255,255,255,.92);     /* chip nằm trên ảnh món */
--pos-shadow-modal: 0 12px 40px rgba(0, 0, 0, 0.25);
--pos-shadow-toast: 0 8px 28px rgba(0, 0, 0, 0.25);
```
> Các token ở mục 2–4 bên dưới (`--pos-spacing-*`, `--pos-radius-*`, `--pos-shadow-sm/md/lg`)
> là thiết kế dự kiến, **chưa có** trong `global.css` (hiện chỉ có `--pos-radius`, `--pos-shadow`).

### 1.6 Kiểm tra tương đối (WCAG AA)
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
