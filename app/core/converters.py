# app/core/converters.py —— 通用类型转换

# 外部库
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # 只用于类型提示，避免 core 层在运行时反向依赖 db 层
    from app.db import BosidengPrice

# 这些类型的值都可以转成 Decimal
DecimalInput = Decimal | int | float | str | None


def to_decimal(value: DecimalInput) -> Decimal | None:
    """把可选值转成 Decimal；已经是 Decimal 的原样返回，None 保持 None。"""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def to_money_text(value: DecimalInput) -> str | None:
    """金额转成两位小数的字符串；None 保持 None。"""
    number = to_decimal(value)
    if number is None:
        return None
    return str(number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def to_percent_text(value: DecimalInput) -> str | None:
    """毛利率（0~1 的比例）转成百分比字符串；None 保持 None。"""
    number = to_decimal(value)
    if number is None:
        return None
    percent = (number * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{percent}%"


def to_ratio_text(value: DecimalInput) -> str | None:
    """把 0~1 的比例转成保留 4 位小数的字符串；None 保持 None。"""
    number = to_decimal(value)
    if number is None:
        return None
    return str(number.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def obj_to_dict(product: "BosidengPrice") -> dict:
    """把 BosidengPrice ORM 对象转成字典，金额 Decimal -> float，方便 JSON 返回。"""
    return {
        "product_code": product.product_code,
        "tag_price": float(product.tag_price),
        "settlement_price": float(product.settlement_price),
        "fee": float(product.fee),
        "pdd_sale_price": float(product.pdd_sale_price),
        "pdd_gross_profit": float(product.pdd_gross_profit),
        "agent_settlement_price": float(product.agent_settlement_price),
        "agent_discount": float(product.agent_discount),
        "agent_profit": float(product.agent_profit),
        "own_profit": float(product.own_profit),
    }
