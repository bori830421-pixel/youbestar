from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from tools.excel_feedback_store import load_excel_feedback, normalize_header_key


FIELD_CATALOG_VERSION = "2026-06-09.generic-excel-v1"
AUTO_MAPPING_SCORE = 0.85
PENDING_MAPPING_SCORE = 0.65
AMBIGUOUS_SCORE_GAP = 0.12


@dataclass(frozen=True)
class StandardField:
    code: str
    label: str
    description: str
    aliases: tuple[str, ...]
    field_type: str = "text"


@dataclass(frozen=True)
class TableCategory:
    code: str
    label: str
    description: str
    evidence: dict[str, float]
    required_groups: tuple[tuple[str, ...], ...]
    target_score: float = 0.75


STANDARD_FIELDS: tuple[StandardField, ...] = (
    StandardField("product_code", "商品编码", "SKU、货号、物料编码或产品编号。", ("商品编码", "货号", "款号", "sku", "SKU", "物料编码", "产品编码", "货品编号", "编号")),
    StandardField("product_name", "商品名称", "商品、产品、物料或货品名称。", ("商品名称", "产品名称", "品名", "货品名称", "物料名称", "名称")),
    StandardField("product_category", "商品分类", "商品所属分类、系列或类目。", ("商品分类", "分类", "类目", "系列", "中文包装")),
    StandardField("brand", "品牌", "商品品牌。", ("品牌", "牌子", "brand")),
    StandardField("product_spec", "产品规格", "商品规格、棋盘规格、型号、材质或文字规格描述。", ("产品规格", "商品规格", "规格", "规格型号", "型号", "棋盘规格", "棋盘尺寸")),
    StandardField("product_size_cm", "产品尺寸(cm)", "单个产品本体的长宽高，通常为 A*B*C 数字格式。", ("产品尺寸", "产品尺寸(cm)", "产品尺寸（cm）", "商品尺寸", "产品长宽高", "棋盘规格", "棋盘尺寸"), "dimension"),
    StandardField("package_size_cm", "包装尺寸(cm)", "单个产品外包装、彩盒或盒规的长宽高。", ("包装尺寸", "包装尺寸(cm)", "包装尺寸（cm）", "彩盒尺寸", "彩盒规格", "盒规", "盒子尺寸"), "dimension"),
    StandardField("inner_box_quantity", "内盒数量", "一大箱中分隔保护产品包装的小内盒/中盒数量，例如 2 或 4。", ("内盒数量", "内盒数", "内箱数", "中盒数", "内盒", "内箱", "中盒"), "number"),
    StandardField("inner_box_size_cm", "内盒尺寸(cm)", "内盒、内箱或中盒的长宽高。", ("内盒尺寸", "内盒规格", "内箱尺寸", "内箱规格", "中盒尺寸", "中盒规格"), "dimension"),
    StandardField("carton_size_cm", "外箱尺寸(cm)", "整箱外箱的长宽高，不是重量。", ("外箱规格", "外箱规格(cm)", "外箱规格（cm）", "外箱尺寸", "外箱尺寸(cm)", "箱规", "箱规尺寸", "箱规尺寸(cm)", "箱规(cm)"), "dimension"),
    StandardField("carton_gross_weight_kg", "箱毛重(kg)", "一整箱货物的毛重。", ("箱毛重", "毛重", "毛", "毛重(kg)", "毛重（kg）", "毛重公斤", "毛重kg"), "number"),
    StandardField("carton_net_weight_kg", "箱净重(kg)", "一整箱货物的净重。", ("箱净重", "净重", "净", "净重(kg)", "净重（kg）", "净重公斤", "净重kg"), "number"),
    StandardField("single_gross_weight_g", "单品毛重(g)", "单个产品的毛重，单位克。", ("单品毛重", "单个毛重", "产品毛重", "单品毛重(g)", "单个产品毛重"), "number"),
    StandardField("single_net_weight_g", "单品净重(g)", "单个产品的净重，单位克。", ("单品净重", "单个净重", "产品净重", "单品净重(g)", "单个产品净重"), "number"),
    StandardField("shipping_packaged_weight_g", "快递包装重量(g)", "产品打包发快递后的重量，单位克。", ("快递包装重量", "打包重量", "发货重量", "包装后重量", "快递重量"), "number"),
    StandardField("dimension_text", "尺寸原文", "无法确定归属的尺寸或规格原文，待用户确认后再拆分。", ("尺寸原文", "规格原文", "尺寸备注"), "text"),
    StandardField("weight_text", "重量原文", "毛净重合并或无法判断毛重/净重时的重量原文。", ("重量原文", "毛净重", "毛/净重", "毛重/净重", "重量", "重量备注"), "text"),
    StandardField("spec", "规格型号", "兼容旧字段：商品规格、型号、尺寸、颜色等规格信息。", ("规格型号", "型号", "参数")),
    StandardField("barcode", "条码", "商品条形码或外部条码。", ("条码", "商品条码", "barcode")),
    StandardField("image_url", "图片链接", "商品图片、SKU 图、主图或实拍图链接。", ("图片", "产品图片", "图片链接", "SKU图", "主图", "实拍图")),
    StandardField("package_type", "包装方式", "商品包装方式。", ("包装", "包装方式", "包装类型")),
    StandardField("pcs_per_carton", "装箱数量", "每箱数量或装箱数。", ("装箱数量", "装箱数", "每箱数量", "pcs/ctn")),
    StandardField("short_name", "商品简称", "商品短名称、内部简称或系统简称。", ("商品简称", "简称", "产品简称", "内部简称")),
    StandardField("sku_code", "规格编码", "SKU 规格、变体、颜色尺码或销售规格编码。", ("规格编码", "SKU编码", "sku编码", "变体编码", "颜色尺码编码", "销售规格编码")),
    StandardField("toy_type", "玩具类型", "玩具行业类型，例如益智、桌游、积木、过家家等。", ("玩具类型", "玩具类别", "玩具品类", "类型")),
    StandardField("customer_name", "客户名称", "客户、买家或采购方名称。", ("客户名称", "客户名", "客户", "买家", "采购方", "客户公司", "名称")),
    StandardField("supplier_name", "供应商名称", "供货方、厂家、工厂或供应商名称。", ("供应商名称", "供应商", "供货商", "厂家", "工厂", "供货方", "名称")),
    StandardField("contact_name", "联系人", "联系人、业务联系人或收货联系人。", ("联系人", "联系人姓名", "业务联系人", "收货联系人")),
    StandardField("salesperson_name", "业务员", "业务员、销售或跟单人员。", ("业务员", "销售", "销售员", "跟单", "业务")),
    StandardField("phone", "电话", "电话、手机或联系电话。", ("电话", "联系电话", "手机", "手机号", "电话号码", "tel", "mobile")),
    StandardField("address", "地址", "客户地址、收货地址或业务地址。", ("地址", "收货地址", "客户地址", "详细地址")),
    StandardField("quantity", "数量", "订单、采购、库存或报价数量。", ("数量", "件数", "qty", "Qty", "QTY", "订购数量", "采购数量")),
    StandardField("unit", "单位", "计量单位，例如件、箱、套、kg。", ("单位", "计量单位", "unit")),
    StandardField("unit_price", "单价", "销售单价、报价单价或采购单价。", ("单价", "报价", "价格", "销售单价", "采购单价", "单价元", "单价(元)", "单价（元）"), "number"),
    StandardField("cost_unit_price", "成本单价", "成本价、出厂价、厂价或品牌价。", ("成本价", "成本单价", "出厂价", "厂价", "厂价RMB", "厂价(RMB)", "品牌价", "成本单价元", "成本价元"), "number"),
    StandardField("standard_price", "标准售价", "商品默认销售价、零售价、标价或标准价。", ("标准售价", "标准价", "零售价", "销售价", "标价", "默认售价"), "number"),
    StandardField("wholesale_price", "批发价", "批量客户、渠道客户或批发业务使用的价格。", ("批发价", "批发价格", "批量价", "渠道价", "经销价"), "number"),
    StandardField("amount", "金额", "合计金额、总价或小计。", ("金额", "总价", "合计", "小计", "总金额", "应收金额", "应付金额"), "number"),
    StandardField("currency", "币种", "CNY、USD 等币种。", ("币种", "币别", "货币", "currency")),
    StandardField("date", "日期", "通用业务日期。", ("日期", "时间", "业务日期", "date")),
    StandardField("remark", "备注", "补充说明或备注。", ("备注", "说明", "note", "Note", "备注说明")),
    StandardField("quote_no", "报价单号", "报价单编号。", ("报价单号", "报价编号", "报价号", "报价单")),
    StandardField("valid_until", "报价有效期", "报价有效日期或截止日期。", ("报价有效期", "有效期", "有效日期", "截止日期")),
    StandardField("moq", "最小起订量", "MOQ 或最低起订量。", ("MOQ", "moq", "最小起订量", "起订量", "最低起订量"), "number"),
    StandardField("order_no", "订单号", "销售订单或客户订单编号。", ("订单号", "订单编号", "客户订单号", "销售订单号")),
    StandardField("order_date", "下单日期", "订单日期或下单时间。", ("下单日期", "订单日期", "下单时间")),
    StandardField("delivery_date", "交货日期", "交期、交货日期或预计到货日期。", ("交货日期", "交期", "交付日期", "预计交期", "预计到货")),
    StandardField("status", "状态", "业务状态、处理状态或订单状态。", ("状态", "订单状态", "处理状态")),
    StandardField("warehouse", "仓库", "仓库或库位。", ("仓库", "库房", "库位", "仓位")),
    StandardField("stock_quantity", "库存数量", "当前库存数量。", ("库存", "库存数量", "现有库存", "在库数量", "库存数"), "number"),
    StandardField("available_quantity", "可用库存", "可售、可用或可分配库存。", ("可用库存", "可售库存", "可用数量"), "number"),
    StandardField("reserved_quantity", "占用库存", "已锁定、预留或占用库存。", ("占用库存", "锁定库存", "预留数量"), "number"),
    StandardField("batch_no", "批次号", "库存、采购或生产批次。", ("批次", "批次号", "批号")),
    StandardField("updated_at", "更新时间", "数据更新时间。", ("更新时间", "更新日期", "最后更新")),
    StandardField("purchase_no", "采购单号", "采购订单编号。", ("采购单号", "采购订单号", "采购编号")),
    StandardField("buyer_name", "采购员", "采购负责人或采购员。", ("采购员", "买手", "采购负责人")),
    StandardField("income_amount", "收入金额", "收入、收款或贷方金额。", ("收入金额", "收入", "收款金额", "贷方金额"), "number"),
    StandardField("expense_amount", "支出金额", "支出、付款或借方金额。", ("支出金额", "支出", "付款金额", "借方金额"), "number"),
    StandardField("output_tax_rate", "销项税率", "销售、报价或财务收款中的销项税率。", ("销项税率", "销项税", "销售税率", "开票税率", "税率"), "number"),
    StandardField("input_tax_rate", "进项税率", "采购、供应商发票或财务付款中的进项税率。", ("进项税率", "进项税", "采购税率", "供应商税率"), "number"),
    StandardField("account_name", "账户名称", "银行、现金或财务账户名称。", ("账户", "账户名称", "银行账户", "科目")),
    StandardField("payment_method", "支付方式", "付款方式、收款方式或支付渠道。", ("支付方式", "付款方式", "收款方式", "支付渠道")),
    StandardField("tracking_no", "物流单号", "运单号、快递单号或跟踪号。", ("物流单号", "运单号", "快递单号", "跟踪号", "tracking")),
    StandardField("carrier", "承运商", "物流公司、快递公司或承运方。", ("承运商", "物流公司", "快递公司", "承运方")),
    StandardField("logistics_status", "物流状态", "发货、运输或签收状态。", ("物流状态", "运输状态", "签收状态")),
    StandardField("ship_date", "发货日期", "发货时间或出库日期。", ("发货日期", "发货时间", "出库日期")),
    StandardField("arrival_date", "到货日期", "到货时间、签收日期或预计到达。", ("到货日期", "到货时间", "签收日期", "预计到达")),
)


TABLE_CATEGORIES: tuple[TableCategory, ...] = (
    TableCategory(
        "quote",
        "报价表",
        "商品报价、工厂报价或客户报价明细。",
        {
            "product_code": 0.22,
            "product_name": 0.18,
            "unit_price": 0.35,
            "cost_unit_price": 0.35,
            "standard_price": 0.28,
            "wholesale_price": 0.28,
            "output_tax_rate": 0.10,
            "amount": 0.10,
            "supplier_name": 0.12,
            "quote_no": 0.28,
            "valid_until": 0.15,
            "moq": 0.10,
            "pcs_per_carton": 0.08,
        },
        (("product_code", "product_name"), ("unit_price", "cost_unit_price")),
    ),
    TableCategory(
        "order",
        "订单表",
        "客户订单、销售订单或订单明细。",
        {
            "order_no": 0.35,
            "customer_name": 0.24,
            "product_code": 0.12,
            "sku_code": 0.10,
            "product_name": 0.12,
            "quantity": 0.16,
            "amount": 0.16,
            "standard_price": 0.10,
            "wholesale_price": 0.10,
            "output_tax_rate": 0.08,
            "order_date": 0.18,
            "delivery_date": 0.15,
            "status": 0.08,
        },
        (("order_no", "customer_name"), ("quantity", "amount", "product_code", "product_name")),
    ),
    TableCategory(
        "inventory",
        "库存表",
        "仓库库存、可用库存或批次库存。",
        {
            "warehouse": 0.22,
            "product_code": 0.16,
            "sku_code": 0.14,
            "product_name": 0.14,
            "stock_quantity": 0.38,
            "available_quantity": 0.26,
            "reserved_quantity": 0.20,
            "batch_no": 0.12,
            "updated_at": 0.08,
        },
        (("product_code", "product_name"), ("stock_quantity", "available_quantity", "warehouse")),
    ),
    TableCategory(
        "customer",
        "客户表",
        "客户档案、联系人或客户资料。",
        {
            "customer_name": 0.44,
            "contact_name": 0.18,
            "phone": 0.18,
            "address": 0.14,
            "remark": 0.05,
        },
        (("customer_name",), ("contact_name", "phone", "address")),
        0.70,
    ),
    TableCategory(
        "product",
        "商品资料表",
        "商品主数据、SKU 档案或物料资料。",
        {
            "product_code": 0.26,
            "sku_code": 0.22,
            "product_name": 0.24,
            "short_name": 0.12,
            "product_category": 0.14,
            "toy_type": 0.16,
            "brand": 0.14,
            "product_spec": 0.18,
            "product_size_cm": 0.12,
            "package_size_cm": 0.10,
            "barcode": 0.14,
            "image_url": 0.08,
            "package_type": 0.08,
            "pcs_per_carton": 0.08,
            "standard_price": 0.12,
            "wholesale_price": 0.12,
        },
        (("product_code", "product_name", "sku_code"), ("product_spec", "product_size_cm", "package_size_cm", "brand", "product_category", "toy_type", "barcode", "package_type", "pcs_per_carton", "short_name")),
        0.72,
    ),
    TableCategory(
        "purchase",
        "采购表",
        "采购订单、供应商采购或采购明细。",
        {
            "purchase_no": 0.34,
            "supplier_name": 0.24,
            "buyer_name": 0.16,
            "product_code": 0.12,
            "sku_code": 0.10,
            "product_name": 0.12,
            "quantity": 0.14,
            "unit_price": 0.12,
            "amount": 0.12,
            "input_tax_rate": 0.10,
            "date": 0.08,
        },
        (("purchase_no", "supplier_name"), ("quantity", "amount", "product_code", "product_name")),
    ),
    TableCategory(
        "finance",
        "财务表",
        "收支、费用、应收应付或流水明细。",
        {
            "income_amount": 0.34,
            "expense_amount": 0.34,
            "output_tax_rate": 0.14,
            "input_tax_rate": 0.14,
            "amount": 0.20,
            "account_name": 0.18,
            "payment_method": 0.14,
            "date": 0.12,
            "remark": 0.05,
        },
        (("income_amount", "expense_amount", "amount"), ("date", "account_name", "payment_method")),
    ),
    TableCategory(
        "logistics",
        "物流表",
        "发货、物流、快递或运输跟踪明细。",
        {
            "tracking_no": 0.36,
            "carrier": 0.26,
            "logistics_status": 0.18,
            "ship_date": 0.14,
            "arrival_date": 0.14,
            "address": 0.10,
            "order_no": 0.08,
        },
        (("tracking_no", "carrier"), ("logistics_status", "ship_date", "arrival_date", "address")),
    ),
)


def _normalize_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("（", "(").replace("）", ")")
    text = re.sub(r"\s+", "", text)
    return re.sub(r"[:：,，;；()（）\[\]【】/\\_\-]+", "", text)


def _alias_index() -> dict[str, list[StandardField]]:
    index: dict[str, list[StandardField]] = {}
    for field in STANDARD_FIELDS:
        aliases = (field.code, field.label, *field.aliases)
        for alias in aliases:
            key = _normalize_key(alias)
            if not key:
                continue
            bucket = index.setdefault(key, [])
            if field not in bucket:
                bucket.append(field)
    return index


ALIAS_INDEX = _alias_index()
FIELD_BY_CODE = {field.code: field for field in STANDARD_FIELDS}
CATEGORY_BY_CODE = {category.code: category for category in TABLE_CATEGORIES}


def standard_field_catalog() -> list[dict[str, Any]]:
    return [
        {
            "code": field.code,
            "label": field.label,
            "description": field.description,
            "aliases": list(field.aliases),
            "field_type": field.field_type,
        }
        for field in STANDARD_FIELDS
    ]


def table_category_catalog() -> list[dict[str, str]]:
    return [
        {
            "code": category.code,
            "label": category.label,
            "description": category.description,
        }
        for category in TABLE_CATEGORIES
    ]


def _field_metadata(field_code: str) -> StandardField | None:
    return FIELD_BY_CODE.get(field_code)


def _suggest_field_code(header: str) -> str:
    clean = _normalize_key(header)
    if not clean:
        return "custom_field"
    token_map = (
        ("包装率", "packing_rate"),
        ("折扣率", "discount_rate"),
        ("税率", "tax_rate"),
        ("汇率", "exchange_rate"),
        ("毛利率", "gross_margin_rate"),
        ("利润率", "profit_rate"),
        ("颜色", "color"),
        ("尺码", "size"),
        ("尺寸", "dimension"),
        ("重量", "weight"),
        ("等级", "grade"),
        ("材质", "material"),
        ("产地", "origin"),
    )
    for token, code in token_map:
        if _normalize_key(token) in clean:
            return code
    digest = hashlib.sha1(clean.encode("utf-8")).hexdigest()[:8]
    return f"custom_field_{digest}"


def _unknown_field_proposal(header: str) -> dict[str, Any] | None:
    clean = str(header or "").strip()
    if not clean or clean.startswith("未命名列"):
        return None
    suggested_code = _suggest_field_code(clean)
    return {
        "type": "new_standard_field",
        "source_header": clean,
        "suggested_field": suggested_code,
        "standard_label": clean,
        "description": f"从原始表头“{clean}”发现的新字段，需要用户确认后才能加入字段目录。",
        "field_type": "number" if any(token in clean for token in ("率", "价", "金额", "数量", "重量")) else "text",
        "needs_confirmation": True,
        "status": "pending_user_confirmation",
    }


def _candidate(field: StandardField, score: float, reason: str) -> dict[str, Any]:
    return {
        "standard_field": field.code,
        "standard_label": field.label,
        "description": field.description,
        "field_type": field.field_type,
        "score": round(score, 2),
        "mapping_score": round(score, 2),
        "reason": reason,
    }


def _merge_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_field: dict[str, dict[str, Any]] = {}
    for item in candidates:
        code = str(item.get("standard_field") or "")
        if not code:
            continue
        existing = by_field.get(code)
        if not existing or float(item.get("score") or 0) > float(existing.get("score") or 0):
            by_field[code] = item
    return sorted(by_field.values(), key=lambda item: float(item.get("score") or 0), reverse=True)


def _scored_mapping_candidates(header: str) -> list[dict[str, Any]]:
    clean_text = str(header or "").strip()
    clean_key = _normalize_key(clean_text)
    if not clean_key:
        return []

    candidates: list[dict[str, Any]] = []
    if "品牌价" in clean_text:
        return [_candidate(FIELD_BY_CODE["cost_unit_price"], 0.98, "品牌价是价格字段，不是品牌。")]
    if "包装规格" in clean_text:
        return _merge_candidates(
            [
                _candidate(FIELD_BY_CODE["product_size_cm"], 0.76, "包装规格常被工厂用作产品长宽高，需要确认。"),
                _candidate(FIELD_BY_CODE["package_size_cm"], 0.74, "包装规格也可能表示彩盒/外包装尺寸，需要确认。"),
                _candidate(FIELD_BY_CODE["dimension_text"], 0.68, "包装规格含义不稳定，保留原文待确认。"),
            ]
        )
    if "棋盘规格" in clean_text or "棋盘尺寸" in clean_text:
        return _merge_candidates(
            [
                _candidate(FIELD_BY_CODE["product_size_cm"], 0.86, "棋盘规格通常表示产品本体尺寸。"),
                _candidate(FIELD_BY_CODE["product_spec"], 0.80, "棋盘规格也可作为产品规格描述。"),
            ]
        )
    if any(token in clean_text for token in ("毛净重", "毛/净重", "毛重/净重", "毛/净", "毛净")):
        return _merge_candidates(
            [
                _candidate(FIELD_BY_CODE["weight_text"], 0.90, "毛净重合并字段需要保留原文并拆分。"),
                _candidate(FIELD_BY_CODE["carton_gross_weight_kg"], 0.78, "合并字段中可能包含箱毛重。"),
                _candidate(FIELD_BY_CODE["carton_net_weight_kg"], 0.78, "合并字段中可能包含箱净重。"),
            ]
        )
    exact_matches = ALIAS_INDEX.get(clean_key, [])
    for field in exact_matches:
        candidates.append(_candidate(field, 0.98, "表头与字段别名精确匹配。"))

    for field in STANDARD_FIELDS:
        aliases = (field.code, field.label, *field.aliases)
        for alias in aliases:
            alias_key = _normalize_key(alias)
            if not alias_key or alias_key == clean_key:
                continue
            if len(alias_key) < 3 or len(clean_key) < 3:
                continue
            if alias_key in clean_key or clean_key in alias_key:
                score = 0.88 if alias_key in clean_key else 0.72
                candidates.append(_candidate(field, score, "表头与字段别名部分匹配。"))
                break

    if "外箱规格" in clean_text or "箱规" in clean_text:
        candidates.append(_candidate(FIELD_BY_CODE["carton_size_cm"], 0.98, "外箱规格/箱规是整箱外箱长宽高。"))
    if "单品克重" in clean_text or "单个克重" in clean_text:
        candidates.extend(
            [
                _candidate(FIELD_BY_CODE["single_gross_weight_g"], 0.76, "单品克重未说明毛/净，需确认。"),
                _candidate(FIELD_BY_CODE["single_net_weight_g"], 0.76, "单品克重未说明毛/净，需确认。"),
                _candidate(FIELD_BY_CODE["weight_text"], 0.70, "单品克重含义不完整，保留原文待确认。"),
            ]
        )
    return _merge_candidates(candidates)


def _mapping_for_header(header: str, feedback: dict[str, Any] | None = None) -> dict[str, Any]:
    clean = str(header or "").strip()
    feedback_mappings = (feedback or {}).get("field_mappings")
    feedback_row = feedback_mappings.get(normalize_header_key(clean)) if isinstance(feedback_mappings, dict) else None
    feedback_field = str((feedback_row or {}).get("standard_field") or "").strip()
    feedback_meta = _field_metadata(feedback_field)
    if feedback_meta:
        return {
            "source_header": clean,
            "standard_field": feedback_meta.code,
            "standard_label": feedback_meta.label,
            "description": feedback_meta.description,
            "field_type": feedback_meta.field_type,
            "confidence": 1.0,
            "mapping_score": 1.0,
            "score_gap": 1.0,
            "status": "mapped",
            "legacy_status": "mapped",
            "needs_confirmation": False,
            "source": "user_feedback",
            "feedback_scope": (feedback_row or {}).get("scope") or "",
            "candidates": [_candidate(feedback_meta, 1.0, "用户确认过的字段映射。")],
        }

    candidates = _scored_mapping_candidates(clean)
    if candidates:
        top = candidates[0]
        second = candidates[1] if len(candidates) > 1 else None
        score = float(top.get("score") or 0)
        score_gap = score - float(second.get("score") or 0) if second else 1.0
        status = "mapped" if score >= AUTO_MAPPING_SCORE and score_gap >= AMBIGUOUS_SCORE_GAP else "pending_confirmation"
        needs_confirmation = status != "mapped"
        field = FIELD_BY_CODE.get(str(top["standard_field"]))
        if field and score >= PENDING_MAPPING_SCORE:
            legacy_status = "mapped" if status == "mapped" else "ambiguous"
            proposal = None
            if needs_confirmation:
                proposal = {
                    "type": "map_existing_field",
                    "source_header": clean,
                    "suggested_field": field.code,
                    "standard_label": field.label,
                    "mapping_score": round(score, 2),
                    "score_gap": round(score_gap, 2),
                    "candidates": candidates[:5],
                    "needs_confirmation": True,
                    "status": "pending_user_confirmation",
                }
            result = {
                "source_header": clean,
                "standard_field": field.code,
                "standard_label": field.label,
                "description": field.description,
                "field_type": field.field_type,
                "confidence": round(score, 2),
                "mapping_score": round(score, 2),
                "score_gap": round(score_gap, 2),
                "status": status,
                "legacy_status": legacy_status,
                "needs_confirmation": needs_confirmation,
                "candidates": candidates[:5],
            }
            if proposal:
                result["proposal"] = proposal
            return result

    matches = ALIAS_INDEX.get(_normalize_key(clean), [])
    if len(matches) == 1:
        field = matches[0]
        return {
            "source_header": clean,
            "standard_field": field.code,
            "standard_label": field.label,
            "description": field.description,
            "field_type": field.field_type,
            "confidence": 0.98,
            "mapping_score": 0.98,
            "score_gap": 1.0,
            "status": "mapped",
            "legacy_status": "mapped",
            "needs_confirmation": False,
            "candidates": [_candidate(field, 0.98, "表头与字段别名精确匹配。")],
        }
    if len(matches) > 1:
        return {
            "source_header": clean,
            "standard_field": "",
            "standard_label": "",
            "confidence": 0.50,
            "mapping_score": 0.50,
            "score_gap": 0.0,
            "status": "pending_confirmation",
            "legacy_status": "ambiguous",
            "needs_confirmation": True,
            "candidates": [
                {
                    "standard_field": field.code,
                    "standard_label": field.label,
                    "description": field.description,
                    "field_type": field.field_type,
                    "score": 0.50,
                }
                for field in matches
            ],
            "proposal": {
                "type": "map_existing_field",
                "source_header": clean,
                "needs_confirmation": True,
                "status": "pending_user_confirmation",
            },
        }

    proposal = _unknown_field_proposal(clean)
    result = {
        "source_header": clean,
        "standard_field": "",
        "standard_label": "",
        "confidence": 0.0,
        "mapping_score": 0.0,
        "score_gap": 0.0,
        "status": "unknown",
        "legacy_status": "unmapped",
        "needs_confirmation": bool(proposal),
        "candidates": candidates[:5],
    }
    if proposal:
        result["proposal"] = proposal
    return result


def _required_groups_met(category: TableCategory, fields: set[str]) -> bool:
    return all(any(field in fields for field in group) for group in category.required_groups)


def _category_candidates(mapped_fields: set[str]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for category in TABLE_CATEGORIES:
        matched_weights = {
            field: weight
            for field, weight in category.evidence.items()
            if field in mapped_fields
        }
        score = sum(matched_weights.values())
        if score <= 0:
            continue
        required_met = _required_groups_met(category, mapped_fields)
        confidence = round(min(0.99, score / category.target_score), 2)
        candidates.append(
            {
                "category": category.code,
                "category_label": category.label,
                "description": category.description,
                "confidence": confidence,
                "required_fields_met": required_met,
                "matched_fields": [
                    {
                        "standard_field": field_code,
                        "standard_label": FIELD_BY_CODE[field_code].label,
                    }
                    for field_code in matched_weights
                ],
                "missing_required_groups": [
                    [FIELD_BY_CODE[field].label for field in group if field in FIELD_BY_CODE]
                    for group in category.required_groups
                    if not any(field in mapped_fields for field in group)
                ],
            }
        )
    return sorted(candidates, key=lambda item: (bool(item["required_fields_met"]), item["confidence"]), reverse=True)


def classify_table(headers: list[str], rows: list[list[str]] | None = None) -> dict[str, Any]:
    feedback = load_excel_feedback(headers)
    field_mappings = [_mapping_for_header(header, feedback) for header in headers]
    mapped_fields = {
        str(mapping["standard_field"])
        for mapping in field_mappings
        if mapping.get("status") in {"mapped", "pending_confirmation"} and mapping.get("standard_field")
    }
    candidates = _category_candidates(mapped_fields)
    proposals = [
        mapping["proposal"]
        for mapping in field_mappings
        if isinstance(mapping.get("proposal"), dict) and mapping.get("needs_confirmation")
    ]

    status = "unknown"
    category = ""
    category_label = "未识别"
    confidence = 0.0
    reasons = [
        "表头与现有字段目录匹配度较低，或缺少可判断业务类型的核心字段。",
        "系统不会把该工作表强行归类为报价表、订单表或其他业务表。",
    ]

    if candidates:
        top = candidates[0]
        second = candidates[1] if len(candidates) > 1 else None
        confidence = float(top["confidence"])
        required_met = bool(top["required_fields_met"])
        second_is_competing = bool(second and (second["required_fields_met"] or not required_met))
        if second_is_competing and confidence >= 0.60 and float(second["confidence"]) >= 0.55 and confidence - float(second["confidence"]) < 0.15:
            status = "ambiguous"
            category_label = "类型不明确"
            reasons = [
                f"可能是{top['category_label']}，也可能是{second['category_label']}，需要用户选择。",
            ]
        elif required_met and confidence >= 0.70:
            status = "recognized"
            category = str(top["category"])
            category_label = str(top["category_label"])
            reasons = [f"识别到{category_label}核心字段，分类证据较充分。"]
        elif confidence >= 0.65:
            status = "partial"
            category = str(top["category"])
            category_label = str(top["category_label"])
            reasons = [
                f"部分字段接近{category_label}，但核心字段不完整或置信度不足。",
                "需要用户确认分类和字段映射后才能标准化归档。",
            ]

    feedback_category = str(feedback.get("category") or "").strip()
    feedback_category_meta = CATEGORY_BY_CODE.get(feedback_category)
    if feedback_category_meta:
        status = "recognized"
        category = feedback_category_meta.code
        category_label = feedback_category_meta.label
        confidence = 1.0
        reasons = [f"已按用户确认过的同类表头模板修正为{category_label}。"]

    return {
        "status": status,
        "category": category,
        "category_label": category_label,
        "confidence": confidence,
        "reasons": reasons,
        "field_mappings": field_mappings,
        "change_proposals": proposals,
        "needs_confirmation": status in {"partial", "ambiguous"} or bool(proposals) or any(
            mapping.get("needs_confirmation") for mapping in field_mappings
        ),
        "candidates": candidates[:3],
        "catalog_version": FIELD_CATALOG_VERSION,
        "available_categories": table_category_catalog(),
        "feedback": {
            "applied": bool(feedback_category_meta) or any(mapping.get("source") == "user_feedback" for mapping in field_mappings),
            "header_signature": feedback.get("header_signature") or "",
        },
    }


def summarize_classifications(sheets: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"recognized": 0, "partial": 0, "ambiguous": 0, "unknown": 0}
    categories: dict[str, int] = {}
    proposal_count = 0
    for sheet in sheets:
        classification = sheet.get("classification") if isinstance(sheet, dict) else {}
        if not isinstance(classification, dict):
            continue
        status = str(classification.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
        category_label = str(classification.get("category_label") or "")
        if classification.get("category") and category_label:
            categories[category_label] = categories.get(category_label, 0) + 1
        proposal_count += len(classification.get("change_proposals") or [])

    return {
        "status_counts": counts,
        "category_counts": categories,
        "change_proposal_count": proposal_count,
        "needs_confirmation": any(
            (sheet.get("classification") or {}).get("needs_confirmation")
            for sheet in sheets
            if isinstance(sheet, dict)
        ),
    }
