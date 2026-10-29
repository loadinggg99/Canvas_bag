# app/services/profit_stats_service.py —— 用 Python 汇总利润统计
#
# 这里不重新定义利润公式，统一复用 analytics_service.calculate_profit，
# 保证统计结果与现有 /api/analytics 的利润口径一致。

# 外部库
from decimal import Decimal

from sqlalchemy import select

# 内部库
from app.db import BosidengPrice, db_session
from app.services.analytics_service import calculate_profit, sort_products

# 重点商品取前几名
TOP_N = 5


def _pick_product_fields(item: dict) -> dict:
    """只保留统计和报告需要的字段，金额继续使用 Decimal。"""
    return {
        "product_code": item["product_code"],
        "pdd_sale_price": item["pdd_sale_price"],
        "pdd_profit": item["pdd_profit"],
        "profit_margin": item["profit_margin"],
    }


def calculate_profit_statistics(products: list[BosidengPrice]) -> dict:
    """对传入的商品列表计算利润统计，返回简单字典。

    商品总数、平均/最高/最低毛利、负毛利数量，以及毛利最高/最低的 5 件商品。
    单件商品利润直接调用 calculate_profit，不修改原有计算口径。
    """
    items = []
    for product in products:
        result = calculate_profit(product)
        items.append(_pick_product_fields(result))

    if not items:
        raise ValueError("没有可统计的商品数据")

    # 复用现有排序函数：按 PDD 毛利从高到低排序
    ranked = sort_products(items, sort_by="pdd_profit")
    profits = [item["pdd_profit"] for item in items]

    # 平均值保留 Decimal 原值；生成报告时再按两位小数展示
    average_profit = sum(profits, Decimal("0")) / Decimal(len(profits))

    return {
        "total": len(items),
        "average_profit": average_profit,
        "max_profit": max(profits),
        "min_profit": min(profits),
        "negative_profit_count": sum(1 for profit in profits if profit < 0),
        # 毛利最高的 5 件
        "top5": ranked[:TOP_N],
        # 毛利最低的 5 件；反过来排列，便于从最低开始阅读
        "bottom5": list(reversed(ranked[-TOP_N:])),
    }


def get_profit_statistics() -> dict:
    """从数据库读取全部商品，再计算利润统计。"""
    with db_session() as db:
        products = db.scalars(select(BosidengPrice)).all()

    return calculate_profit_statistics(products)


if __name__ == "__main__":
    # 单独测试：.venv/bin/python -m app.services.profit_stats_service
    from pprint import pprint

    pprint(get_profit_statistics())
