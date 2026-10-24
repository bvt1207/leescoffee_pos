import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate


class LeescoffeeMenu(Document):
    """Quản lý menu và danh sách món dùng cho POS."""

    def validate(self):
        if not self.items:
            frappe.throw(
                _("Menu {0} phải có ít nhất 1 món.").format(
                    self.menu_name or self.name
                )
            )

        # Đồng bộ lại thông tin từng món trước khi lưu Menu.
        for row in self.items:
            row.load_item_details(parent_doc=self)

    # ------------------------------------------------------------------
    # Helpers lấy sizes (biến thể) cho món
    # ------------------------------------------------------------------

    @staticmethod
    def _get_item_variants_batch(template_codes):
        """Trả về dict {template_code: [variants]} cho nhiều template cùng lúc.

        Template = has_variants=1 và variant_of rỗng.
        Mỗi biến thể là 1 Item có variant_of = template_code, lấy thuộc tính
        Size qua Item Attribute Value (abbr = label, idx = thứ tự sắp xếp).
        Danh sách variants đã sort theo idx, label.
        """
        if not template_codes:
            return {}

        variants = frappe.get_all(
            "Item",
            filters={"variant_of": ("in", list(template_codes)), "disabled": 0},
            fields=["name", "variant_of"],
            order_by="name asc",
        )
        if not variants:
            return {code: [] for code in template_codes}

        variant_names = [v.name for v in variants]

        # 1) Giá trị Size của từng biến thể (vd: Americano-L -> "L")
        variant_attrs = frappe.get_all(
            "Item Variant Attribute",
            filters={
                "parent": ("in", variant_names),
                "parenttype": "Item",
                "attribute": "Size",
            },
            fields=["parent", "attribute_value"],
        )

        # 2) Tra abbr + idx của từng giá trị trong Item Attribute "Size"
        size_values = frappe.get_all(
            "Item Attribute Value",
            filters={"parent": "Size"},
            fields=["attribute_value", "abbr", "idx"],
        )
        size_map = {s.attribute_value: s for s in size_values}

        value_by_variant = {}
        for a in variant_attrs:
            s = size_map.get(a.attribute_value)
            value_by_variant[a.parent] = {
                "label": (s.abbr if s else None) or a.attribute_value or "",
                "idx": (s.idx if s else 0) or 0,
            }

        result = {code: [] for code in template_codes}
        for v in variants:
            template = v.variant_of
            info = value_by_variant.get(v.name, {"label": v.name, "idx": 0})
            result.setdefault(template, []).append(
                {
                    "item_code": v.name,
                    "label": info["label"] or v.name,
                    "idx": info["idx"],
                }
            )

        for template in result:
            result[template].sort(key=lambda x: (x["idx"], x["label"]))

        return result

    @staticmethod
    def _get_item_prices(item_codes, price_list):
        """Lấy Item Price cho nhiều item_code cùng 1 Price List (1 query, không lặp).

        Trả về dict {item_code: rate_float_or_None}.
        Chỉ lấy giá còn hiệu lực hôm nay (valid_from <= today <= valid_upto,
        NULL được coi là luôn hiệu lực).
        """
        if not item_codes or not price_list:
            return {}

        today = getdate(nowdate())

        rows = frappe.get_all(
            "Item Price",
            filters={
                "item_code": ("in", list(item_codes)),
                "price_list": price_list,
                "selling": 1,
                "currency": "VND",
            },
            fields=["item_code", "price_list_rate", "valid_from", "valid_upto"],
            order_by="valid_from desc",
        )

        result = {}
        for code in item_codes:
            result[code] = None

        for row in rows:
            code = row.item_code
            valid_from = getdate(row.valid_from) if row.valid_from else None
            valid_upto = getdate(row.valid_upto) if row.valid_upto else None

            if valid_from and valid_from > today:
                continue
            if valid_upto and valid_upto < today:
                continue

            # Chỉ cập nhật nếu chưa có hoặc bản ghi mới hơn (order_by valid_from desc
            # đã đưa bản ghi mới nhất lên đầu, nên lấy lần đầu tiên là đủ).
            if result[code] is None:
                result[code] = float(row.price_list_rate or 0)

        return result

    @staticmethod
    def _build_item_payload(menu_item_row, price_map, item_info, variants_map):
        """Xây payload 1 món cho POS UI.

        Trả về dict:
            {template, name, image, sizes: [{label, item_code, rate}]}
        - template: True nếu item là template (has_variants=1, variant_of rỗng).
        - name: tên item_code.
        - image: ảnh sản phẩm của Item (hoặc None).
        - sizes: danh sách biến thể; Item thường -> 1 phần tử.
        - rate: lấy từ Item Price theo Price List của menu (trong price_map),
          None nếu chưa có giá. Không trả giá ở cấp item (chỉ trả trong sizes).
        """
        item_code = menu_item_row.get("item_code")
        if not item_code:
            return None

        info = item_info.get(item_code)
        if not info or info.get("disabled"):
            return None

        is_template = bool(info.get("has_variants") and not info.get("variant_of"))

        sizes = []
        if is_template:
            variants = variants_map.get(item_code, [])
            for v in variants:
                sizes.append(
                    {
                        "label": v["label"],
                        "item_code": v["item_code"],
                        "rate": price_map.get(v["item_code"]),
                    }
                )
        else:
            sizes.append(
                {
                    "label": "",
                    "item_code": item_code,
                    "rate": price_map.get(item_code),
                }
            )

        return {
            "template": is_template,
            "name": info.get("item_name") or item_code,
            "image": info.get("image") or None,
            "sizes": sizes,
        }

    @staticmethod
    def get_menu_with_items(price_list=None):
        """Lấy danh sách menu kèm các món đã cấu hình (payload kèm sizes).

        Mỗi item trả: {template, name, image, sizes: [{label, item_code, rate}]}.
        - Template: sizes = các biến thể (variant_of = template).
        - Item thường: sizes = 1 phần tử.
        - rate lấy từ Item Price theo Price List của menu; null nếu chưa có giá.
        Không trả giá ở cấp item.
        Query Item Price được gom (1 query cho tất cả item_code của menu).
        """
        filters = {}
        if price_list:
            filters["price_list"] = price_list

        menus = frappe.get_all(
            "Leescoffee Menu",
            filters=filters,
            fields=["name", "menu_name", "price_list"],
        )

        result = []

        for menu in menus:
            menu_items = frappe.get_all(
                "Leescoffee Menu Item",
                filters={
                    "parent": menu.name,
                    "parenttype": "Leescoffee Menu",
                    "parentfield": "items",
                },
                fields=[
                    "idx",
                    "item_code",
                    "item_name",
                    "item_type",
                    "price",
                ],
                order_by="idx asc",
            )

            # Chuẩn bị list row + gom item_code (không query Item trong vòng lặp)
            item_rows = []
            item_codes = set()
            template_codes = set()

            for row in menu_items:
                row_dict = dict(row)
                row_dict["price_list"] = menu.price_list
                item_rows.append(row_dict)
                item_codes.add(row_dict["item_code"])

            # 1 query Item info cho tất cả item_code của menu
            item_info = {}
            if item_codes:
                for doc in frappe.get_all(
                    "Item",
                    filters={"name": ("in", list(item_codes))},
                    fields=[
                        "name",
                        "item_name",
                        "image",
                        "has_variants",
                        "variant_of",
                        "disabled",
                    ],
                ):
                    item_info[doc.name] = doc

                # Phân loại template vs Item thường
                for code, info in item_info.items():
                    if info.disabled:
                        continue
                    if info.has_variants and not info.variant_of:
                        template_codes.add(code)

            # 1 query variants của tất cả template (batch)
            variants_map = LeescoffeeMenu._get_item_variants_batch(list(template_codes))

            # Gom tất cả item_code cần lấy giá:
            # - Item thường: chính nó
            # - Template: các variant của nó
            all_codes = set()
            for row_dict in item_rows:
                code = row_dict["item_code"]
                info = item_info.get(code)
                if not info or info.disabled:
                    continue
                if info.has_variants and not info.variant_of:
                    for v in variants_map.get(code, []):
                        all_codes.add(v["item_code"])
                else:
                    all_codes.add(code)

            # 1 query Item Price cho tất cả item_code
            price_map = LeescoffeeMenu._get_item_prices(list(all_codes), menu.price_list)

            items_payload = []
            for row_dict in item_rows:
                payload = LeescoffeeMenu._build_item_payload(
                    row_dict, price_map, item_info, variants_map
                )
                if payload:
                    items_payload.append(payload)

            result.append(
                {
                    "name": menu.name,
                    "menu_name": menu.menu_name,
                    "price_list": menu.price_list,
                    "items": items_payload,
                }
            )

        return result

    @staticmethod
    def get_price_for_item(item_code, price_list):
        """Lấy giá bán có hiệu lực theo Item và Price List."""
        if not item_code or not frappe.db.exists("Item", item_code):
            frappe.throw(
                _("Item {0} không tồn tại.").format(item_code or "")
            )

        if not price_list:
            return None

        item = frappe.db.get_value(
            "Item",
            item_code,
            ["disabled", "has_variants", "variant_of"],
            as_dict=True,
        )

        if item.disabled:
            frappe.throw(
                _("Item {0} đã bị vô hiệu hóa.").format(item_code)
            )

        # Item Template không có giá bán trực tiếp.
        if item.has_variants and not item.variant_of:
            return None

        today = getdate(nowdate())

        item_prices = frappe.get_all(
            "Item Price",
            filters={
                "item_code": item_code,
                "price_list": price_list,
                "selling": 1,
                "currency": "VND",
            },
            fields=["price_list_rate", "valid_from", "valid_upto"],
            order_by="valid_from desc",
        )

        for item_price in item_prices:
            valid_from = (
                getdate(item_price.valid_from)
                if item_price.valid_from
                else None
            )
            valid_upto = (
                getdate(item_price.valid_upto)
                if item_price.valid_upto
                else None
            )

            if valid_from and valid_from > today:
                continue

            if valid_upto and valid_upto < today:
                continue

            return float(item_price.price_list_rate or 0)

        return None