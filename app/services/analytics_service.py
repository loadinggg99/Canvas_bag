# app/services/analytics_service.py —— 利润计算、排序和异常检测

# 内部库
from typing import TYPE_CHECKING

# 外部库
from decimal import Decimal

if TYPE_CHECKING:
    # 只用于类型提示，避免业务层在运行时依赖数据库层
    from app.db import BosidengPrice

# 暂定规则：原表 PDD 毛利额外扣减 10 元
# 确认这 10 元的实际业务含义后，再修改此配置。
FIXED_DEDUCTION = Decimal("10")

# 示例阈值，不是行业标准，可根据业务需求调整。
LOW_PROFIT_MARGIN_THRESHOLD = Decimal("0.05")


def calculate_profit_at_price(
    product: "BosidengPrice",
    price: Decimal | None,
) -> dict:
    """按指定售价计算单个商品的 PDD 毛利及毛利率。

    公式只在这里维护一次；原价利润和调价模拟都调用它，
    避免两个地方各写一份公式后逐渐不一致。
    """
    cost = product.settlement_price
    fee = product.fee

    if price is None or price <= 0:
        raise ValueError("拼多多售价缺失或无效（必须大于 0）")

    if cost is None or fee is None:
        raise ValueError("二级结算价或费用缺失")

    pdd_profit = price - cost - fee - FIXED_DEDUCTION
    profit_margin = pdd_profit / price

    return {
        "product_code": product.product_code,
        "pdd_sale_price": price,
        "pdd_profit": pdd_profit,
        "profit_margin": profit_margin,
    }


def calculate_profit(product: "BosidengPrice") -> dict:
    """按商品当前拼多多售价计算毛利及毛利率。"""
    return calculate_profit_at_price(product, product.pdd_sale_price)


def sort_products(
    products: list[dict],
    sort_by: str = "pdd_profit",
) -> list[dict]:
    """对已经计算利润的商品结果排序。"""
    allowed_fields = [
        "pdd_profit",
        "pdd_sale_price",
        "profit_margin",
    ]

    if sort_by not in allowed_fields:
        raise ValueError(f"不支持的排序字段：{sort_by}")

    # 缺失值放最后
    return sorted(
        products,
        key=lambda item: (
            item[sort_by] is None,
            item[sort_by] if item[sort_by] is not None else Decimal(0),
        ),
        reverse=True,
    )


def detect_anomalies(
    result: dict,
    margin_threshold: Decimal = LOW_PROFIT_MARGIN_THRESHOLD,
) -> list[dict]:
    """根据单个商品的利润计算结果检测利润异常。

    margin_threshold 允许调用方传入自己的毛利率阈值；
    不传时继续使用原来的 LOW_PROFIT_MARGIN_THRESHOLD。
    """
    anomalies = []

    profit = result["pdd_profit"]
    margin = result["profit_margin"]

    # 毛利为负的异常处理
    if profit < 0:
        anomalies.append({
            "code": "NEGATIVE_PROFIT",
            "severity": "high",
            "message": "PDD 毛利为负",
        })

    # 毛利率低于设定阈值异常处理
    if margin < margin_threshold:
        anomalies.append({
            "code": "LOW_PROFIT_MARGIN",
            "severity": "medium",
            "message": "PDD 毛利率低于设定阈值",
        })

    return anomalies


def analytics_products(products: list) -> dict:
    """批量计算利润、检测异常，并按 PDD 毛利从高到低排列。"""
    items = []

    for product in products:
        result = calculate_profit(product)
        result["anomalies"] = detect_anomalies(result)
        items.append(result)

    items = sort_products(items, sort_by="pdd_profit")

    return {
        "total": len(items),
        "sort_by": "pdd_profit",
        "items": items,
    }
