# app/services/simulations.py 接收 ORM 查询得到的商品对象，再接收用户希望模拟的售价

# 外部库
from decimal import Decimal

# 内部库
from app.core import to_money_text, to_ratio_text
from app.services.analytics_service import (
    calculate_profit,
    calculate_profit_at_price,
)

def simulate_price(
        product,
        target_price: Decimal,
        target_margin: Decimal | None = None,
        min_price: Decimal | None = None,
        max_price: Decimal| None = None,
) -> dict:
    """模拟修改拼多多售价后的利润变化"""
    if not isinstance(target_price, Decimal):
        raise TypeError("target_price 必须是 Decimal")

    if target_price <= 0:
        raise ValueError("模拟售价必须大于 0")

    if target_margin is not None and not (
            Decimal("0") <= target_margin < Decimal("1")
    ):
        raise ValueError("目标毛利率必须在 0 到 1 之间，不含 1")

    if min_price is not None and max_price is not None:
        if min_price > max_price:
            raise ValueError("最低售价不能高于最高售价")

    if min_price is not None and target_price < min_price:
        raise ValueError("模拟售价低于最低售价")

    if max_price is not None and target_price > max_price:
        raise ValueError("模拟售价高于最高售价")

    # 使用统一的原价利润计算口径
    original = calculate_profit(product)

    # 调价后的利润也复用同一个公式函数，避免两处公式不一致
    simulated = calculate_profit_at_price(product, target_price)
    simulated_profit = simulated["pdd_profit"]
    simulated_margin = simulated["profit_margin"]

    violations = []

    if target_margin is not None and simulated_margin < target_margin:
        violations.append({
            "code": "TARGET_MARGIN_NOT_MET",
            "message": "模拟毛利率未达到目标",
        })

    return {
        "product_code": product.product_code,
        "original_price": to_money_text(original["pdd_sale_price"]),
        "target_price": to_money_text(target_price),
        "original_profit": to_money_text(original["pdd_profit"]),
        "simulated_profit": to_money_text(simulated_profit),
        "profit_change": to_money_text(
            simulated_profit - original["pdd_profit"]
        ),
        "profit_margin": to_ratio_text(simulated_margin),
        "feasible": len(violations) == 0,
        "violations": violations,
    }
