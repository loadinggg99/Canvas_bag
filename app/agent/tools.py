# app/agent/tools.py —— Agent 可调用的 5 个只读工具
#
# 这个文件只做三件事：
# 1. 接收大模型传来的参数；
# 2. 复用 services 层已有的查询、利润计算和模拟函数；
# 3. 把 Decimal 转成字符串，返回 JSON 兼容的字典。
#
# 数据库 Session 在工具内部创建和释放，不作为大模型可以填写的参数。

# 内部库
from app.core import to_decimal, to_money_text, to_percent_text, to_ratio_text
from app.db import BosidengPrice, db_session
from app.schemas.agent_tools import (
    CheckPricingRisksInput,
    CompareProductsInput,
    QueryProductsInput,
    SimulatePriceInput,
)
from app.services import simulations as simulation_service
from app.services.analytics_service import (
    LOW_PROFIT_MARGIN_THRESHOLD,
    calculate_profit,
    detect_anomalies,
)
from app.services.profit_stats_service import get_profit_statistics

# 外部库
from decimal import Decimal
from typing import Literal

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError


# ============ 通用类型转化工具 ============

def _to_output(item: dict) -> dict:
    """把内部 Decimal 字典转成方便 JSON / 大模型阅读的字典。"""
    output = {
        "product_code": item["product_code"],
        "pdd_sale_price": to_money_text(item["pdd_sale_price"]),
        "pdd_profit": to_money_text(item["pdd_profit"]),
        "profit_margin": to_ratio_text(item["profit_margin"]),
        "profit_margin_percent": to_percent_text(item["profit_margin"]),
    }

    # 利润统计结果里没有吊牌价，有这一项时才返回
    if "tag_price" in item:
        output["tag_price"] = to_money_text(item["tag_price"])

    return output


def _product_metrics(product: BosidengPrice) -> dict:
    """调用现有利润函数，返回内部使用的 Decimal 指标。"""
    result = calculate_profit(product)
    return {
        "product_code": result["product_code"],
        "tag_price": product.tag_price,
        "pdd_sale_price": result["pdd_sale_price"],
        "pdd_profit": result["pdd_profit"],
        "profit_margin": result["profit_margin"],
    }


def _db_error(exc: SQLAlchemyError) -> dict:
    """数据库错误只返回类型，不把连接串等细节交给大模型。"""
    return {
        "error": "数据库操作失败，请检查数据库连接。",
        "error_type": type(exc).__name__,
    }


# ============ 1. 商品查询 ============

@tool(args_schema=QueryProductsInput)
def query_products(
    product_code: str | None = None,
    min_profit: float | None = None,
    max_profit: float | None = None,
    min_sale_price: float | None = None,
    max_sale_price: float | None = None,
    sort_by: Literal["pdd_profit", "profit_margin", "pdd_sale_price"] = "pdd_profit",
    descending: bool = True,
    limit: int = 10,
) -> dict:
    """查询商品，并按毛利或售价筛选、排序。

    什么时候调用：
    - 用户给出货号，想知道商品的价格和利润；
    - 用户想找“毛利在 200 到 500 元之间”或“售价低于 1000 元”的商品；
    - 用户想看毛利最高/最低的前几个商品。

    返回：
    - matched_count：筛选后匹配的商品总数；
    - returned_count：实际返回数量（受 limit 限制）；
    - skipped_count：因价格等数据无效而无法计算利润的商品数；
    - items：商品列表，金额是两位小数字符串，毛利率是 0~1 的小数。
    """
    # 先把用户输入转成 Decimal，后面的比较全部使用 Decimal
    min_profit_value = to_decimal(min_profit)
    max_profit_value = to_decimal(max_profit)
    min_sale_value = to_decimal(min_sale_price)
    max_sale_value = to_decimal(max_sale_price)

    if (
        min_profit_value is not None
        and max_profit_value is not None
        and min_profit_value > max_profit_value
    ):
        return {"error": "最低毛利不能高于最高毛利"}

    if (
        min_sale_value is not None
        and max_sale_value is not None
        and min_sale_value > max_sale_value
    ):
        return {"error": "最低售价不能高于最高售价"}

    try:
        with db_session() as db:
            stmt = select(BosidengPrice)

            if product_code:
                # 部分匹配，用户只记得货号的一部分也能查到
                stmt = stmt.where(
                    BosidengPrice.product_code.like(f"%{product_code}%")
                )

            products = db.scalars(stmt).all()

            rows = []
            skipped_count = 0

            for product in products:
                try:
                    result = calculate_profit(product)
                except (ValueError, ArithmeticError):
                    # 单条数据有问题时不中断整个查询，只记录跳过数量
                    skipped_count += 1
                    continue

                if (
                    min_profit_value is not None
                    and result["pdd_profit"] < min_profit_value
                ):
                    continue
                if (
                    max_profit_value is not None
                    and result["pdd_profit"] > max_profit_value
                ):
                    continue
                if (
                    min_sale_value is not None
                    and result["pdd_sale_price"] < min_sale_value
                ):
                    continue
                if (
                    max_sale_value is not None
                    and result["pdd_sale_price"] > max_sale_value
                ):
                    continue

                rows.append({
                    "product_code": result["product_code"],
                    "tag_price": product.tag_price,
                    "pdd_sale_price": result["pdd_sale_price"],
                    "pdd_profit": result["pdd_profit"],
                    "profit_margin": result["profit_margin"],
                })

    except SQLAlchemyError as exc:
        return _db_error(exc)

    # 排序后再截断，保证返回的是排序后的前 limit 条
    rows.sort(key=lambda item: item[sort_by], reverse=descending)
    matched_count = len(rows)
    selected = rows[:limit]

    return {
        "matched_count": matched_count,
        "returned_count": len(selected),
        "skipped_count": skipped_count,
        "sort_by": sort_by,
        "descending": descending,
        "items": [_to_output(item) for item in selected],
    }


# ============ 2. 利润分析 ============

@tool
def analyze_profit() -> dict:
    """统计全表商品的利润情况，不需要任何参数。

    什么时候调用：
    - 用户问“整体利润怎么样”“平均毛利是多少”“有没有负毛利商品”；
    - 用户想要利润分析报告的数据基础（重点商品、最高/最低毛利等）。

    返回：
    - total：商品总数；
    - average_profit / max_profit / min_profit：平均、最高、最低毛利；
    - negative_profit_count：负毛利商品数量；
    - top5 / bottom5：毛利最高和最低的各 5 件商品。

    本工具直接调用已有的 get_profit_statistics，不重新编写统计逻辑。
    """
    try:
        statistics = get_profit_statistics()
    except ValueError as exc:
        return {"error": str(exc)}
    except SQLAlchemyError as exc:
        return _db_error(exc)

    return {
        "total": statistics["total"],
        "average_profit": to_money_text(statistics["average_profit"]),
        "max_profit": to_money_text(statistics["max_profit"]),
        "min_profit": to_money_text(statistics["min_profit"]),
        "negative_profit_count": statistics["negative_profit_count"],
        "top5": [_to_output(item) for item in statistics["top5"]],
        "bottom5": [_to_output(item) for item in statistics["bottom5"]],
        "sort_by": "pdd_profit",
    }


# ============ 3. 定价模拟 ============

@tool(args_schema=SimulatePriceInput)
def simulate_price(product_code: str, target_price: float) -> dict:
    """模拟修改商品售价后，毛利和毛利率会变成多少。

    什么时候调用：
    - 用户说“把这个货号降到/涨到某个价格，利润会怎样”；
    - 用户想知道调价前后的售价、毛利、毛利率和变化量。

    返回：
    - original_price / target_price / price_change：原售价、目标售价、售价变化；
    - original_profit / simulated_profit / profit_change：原毛利、模拟毛利、毛利变化；
    - original_profit_margin / simulated_profit_margin / profit_margin_change：
      原毛利率、模拟毛利率、毛利率变化（0~1 的小数）；
    - feasible / violations：现有模拟函数的可行性和违规提示。

    利润和毛利率全部由 Python 使用 Decimal 计算，再交给本工具包装；
    不把数据库 Session 暴露给大模型。
    """
    target_price_value = to_decimal(target_price)
    if target_price_value is None:
        return {"error": "目标售价不能为空"}

    try:
        with db_session() as db:
            product = db.get(BosidengPrice, product_code)

            if product is None:
                return {"error": f"找不到货号 {product_code}"}

            # 原利润统一复用 analytics_service.calculate_profit
            original = calculate_profit(product)

            try:
                # 模拟利润复用 simulations.simulate_price，不复制利润公式
                result = simulation_service.simulate_price(
                    product=product,
                    target_price=target_price_value,
                )
            except (TypeError, ValueError) as exc:
                return {"error": str(exc)}

    except SQLAlchemyError as exc:
        return _db_error(exc)

    original_price = Decimal(result["original_price"])
    original_margin = original["profit_margin"]
    simulated_margin = Decimal(result["profit_margin"])
    margin_change = simulated_margin - original_margin

    return {
        "product_code": result["product_code"],
        "original_price": result["original_price"],
        "target_price": result["target_price"],
        "price_change": to_money_text(target_price_value - original_price),
        "original_profit": result["original_profit"],
        "simulated_profit": result["simulated_profit"],
        "profit_change": result["profit_change"],
        "original_profit_margin": to_ratio_text(original_margin),
        "original_profit_margin_percent": to_percent_text(original_margin),
        "simulated_profit_margin": result["profit_margin"],
        "simulated_profit_margin_percent": to_percent_text(simulated_margin),
        "profit_margin_change": to_ratio_text(margin_change),
        "feasible": result["feasible"],
        "violations": result["violations"],
    }


# ============ 4. 定价风险检查 ============

@tool(args_schema=CheckPricingRisksInput)
def check_pricing_risks(
    product_code: str | None = None,
    margin_threshold: float | None = None,
    limit: int = 20,
) -> dict:
    """检查商品的负毛利、售价异常和必要字段缺失等定价风险。

    什么时候调用：
    - 用户问“哪些商品有定价风险”“有没有负毛利商品”；
    - 用户想按自己设定的毛利率阈值筛查商品；
    - 用户想在改价前检查商品数据是否完整、价格是否异常。

    检查规则（全部由 Python 判断，不由大模型猜测）：
    - 缺少售价、吊牌价、二级结算价或费用；
    - 售价 <= 0，或者二级结算价/费用为负数；
    - 拼多多售价高于吊牌价（价格倒挂，仅提示，需业务确认）；
    - 毛利为负；
    - 毛利率低于 margin_threshold；不传时使用服务层的默认阈值。

    返回：
    - scanned_count：实际检查的商品数；
    - risk_product_count：存在风险的商品数；
    - margin_threshold / margin_threshold_percent：本次使用的阈值；
    - items：有风险的商品和对应的风险列表，最多 limit 条。
    """
    threshold = to_decimal(margin_threshold)
    if threshold is None:
        threshold = LOW_PROFIT_MARGIN_THRESHOLD

    try:
        with db_session() as db:
            stmt = select(BosidengPrice)
            if product_code:
                stmt = stmt.where(
                    BosidengPrice.product_code.like(f"%{product_code}%")
                )
            products = db.scalars(stmt).all()

    except SQLAlchemyError as exc:
        return _db_error(exc)

    if not products:
        if product_code:
            return {"error": f"找不到货号 {product_code}"}
        return {"error": "没有可检查的商品数据"}

    risk_items = []

    for product in products:
        risks = []

        # 1. 必要字段缺失。ORM 当前是非空列，这里仍然防御性检查。
        required_fields = {
            "pdd_sale_price": product.pdd_sale_price,
            "tag_price": product.tag_price,
            "settlement_price": product.settlement_price,
            "fee": product.fee,
        }
        missing_fields = [
            field_name
            for field_name, value in required_fields.items()
            if value is None
        ]
        if missing_fields:
            risks.append({
                "code": "MISSING_REQUIRED_FIELDS",
                "severity": "high",
                "message": f"缺少必要字段：{', '.join(missing_fields)}",
            })

        sale_price = product.pdd_sale_price
        tag_price = product.tag_price
        settlement_price = product.settlement_price
        fee = product.fee

        # 2. 售价异常：售价必须大于 0
        if sale_price is not None and sale_price <= 0:
            risks.append({
                "code": "INVALID_SALE_PRICE",
                "severity": "high",
                "message": "拼多多售价小于或等于 0",
            })

        # 3. 售价高于吊牌价。该规则是否算异常还需业务确认，因此只提示。
        if (
            sale_price is not None
            and tag_price is not None
            and tag_price > 0
            and sale_price > tag_price
        ):
            risks.append({
                "code": "SALE_PRICE_ABOVE_TAG_PRICE",
                "severity": "medium",
                "message": "拼多多售价高于吊牌价，请确认是否为价格异常",
            })

        if tag_price is not None and tag_price <= 0:
            risks.append({
                "code": "INVALID_TAG_PRICE",
                "severity": "medium",
                "message": "吊牌价小于或等于 0，无法判断价格是否异常",
            })

        if settlement_price is not None and settlement_price < 0:
            risks.append({
                "code": "INVALID_SETTLEMENT_PRICE",
                "severity": "high",
                "message": "二级结算价为负数",
            })

        if fee is not None and fee < 0:
            risks.append({
                "code": "INVALID_FEE",
                "severity": "high",
                "message": "费用为负数",
            })

        # 4. 只有售价、结算价、费用都可用时才计算利润和毛利率
        calculated = None
        if (
            sale_price is not None
            and sale_price > 0
            and settlement_price is not None
            and fee is not None
        ):
            try:
                calculated = calculate_profit(product)
            except (ValueError, ArithmeticError) as exc:
                risks.append({
                    "code": "CALCULATION_ERROR",
                    "severity": "high",
                    "message": f"利润计算失败：{type(exc).__name__}",
                })
            else:
                # 负毛利、低毛利直接复用现有 detect_anomalies
                risks.extend(
                    detect_anomalies(
                        calculated,
                        margin_threshold=threshold,
                    )
                )

        if not risks:
            continue

        if calculated is None:
            pdd_profit = None
            profit_margin = None
        else:
            pdd_profit = calculated["pdd_profit"]
            profit_margin = calculated["profit_margin"]

        risk_items.append({
            "product_code": product.product_code,
            "pdd_sale_price": to_money_text(sale_price),
            "pdd_profit": to_money_text(pdd_profit),
            "profit_margin": to_ratio_text(profit_margin),
            "profit_margin_percent": to_percent_text(profit_margin),
            "risks": risks,
        })

    # 输出顺序保持稳定，方便测试和阅读
    risk_items.sort(key=lambda item: item["product_code"])
    selected = risk_items[:limit]

    return {
        "scanned_count": len(products),
        "risk_product_count": len(risk_items),
        "returned_count": len(selected),
        "margin_threshold": to_ratio_text(threshold),
        "margin_threshold_percent": to_percent_text(threshold),
        "items": selected,
    }


# ============ 5. 商品利润对比 ============

@tool(args_schema=CompareProductsInput)
def compare_products(product_codes: list[str]) -> dict:
    """对比多个商品的售价、毛利和毛利率。

    什么时候调用：
    - 用户一次给出几个货号，想横向比较哪个更赚钱；
    - 用户想知道这几个商品中谁的毛利最高、毛利率最低。

    返回：
    - requested_codes：去重后的请求货号；
    - found_count：找到并成功计算的商品数；
    - missing_codes / failed_codes：数据库里没有的货号、计算失败的货号；
    - items：每个商品的售价、毛利、毛利率（结构化列表）；
    - comparison：毛利/毛利率最高最低的商品和差值。

    所有金额比较和差值都由 Python 使用 Decimal 计算。
    """
    # 去重并保持用户输入顺序
    codes = []
    for code in product_codes:
        code = code.strip()
        if code and code not in codes:
            codes.append(code)

    if len(codes) < 2:
        return {"error": "请至少提供 2 个不同的商品货号"}

    try:
        with db_session() as db:
            products = db.scalars(
                select(BosidengPrice).where(
                    BosidengPrice.product_code.in_(codes)
                )
            ).all()
    except SQLAlchemyError as exc:
        return _db_error(exc)

    product_map = {product.product_code: product for product in products}

    items = []
    missing_codes = []
    failed_codes = []

    # 按用户输入顺序输出，方便和问题一一对应
    for code in codes:
        product = product_map.get(code)

        if product is None:
            missing_codes.append(code)
            continue

        try:
            items.append(_product_metrics(product))
        except (ValueError, ArithmeticError):
            failed_codes.append(code)

    comparison = {}
    if items:
        highest_profit_item = max(items, key=lambda item: item["pdd_profit"])
        lowest_profit_item = min(items, key=lambda item: item["pdd_profit"])
        highest_margin_item = max(items, key=lambda item: item["profit_margin"])
        lowest_margin_item = min(items, key=lambda item: item["profit_margin"])

        comparison = {
            "highest_profit_product": highest_profit_item["product_code"],
            "highest_profit": to_money_text(highest_profit_item["pdd_profit"]),
            "lowest_profit_product": lowest_profit_item["product_code"],
            "lowest_profit": to_money_text(lowest_profit_item["pdd_profit"]),
            "profit_spread": to_money_text(
                highest_profit_item["pdd_profit"] - lowest_profit_item["pdd_profit"]
            ),
            "highest_margin_product": highest_margin_item["product_code"],
            "highest_margin": to_ratio_text(highest_margin_item["profit_margin"]),
            "highest_margin_percent": to_percent_text(
                highest_margin_item["profit_margin"]
            ),
            "lowest_margin_product": lowest_margin_item["product_code"],
            "lowest_margin": to_ratio_text(lowest_margin_item["profit_margin"]),
            "lowest_margin_percent": to_percent_text(
                lowest_margin_item["profit_margin"]
            ),
            "margin_spread": to_ratio_text(
                highest_margin_item["profit_margin"]
                - lowest_margin_item["profit_margin"]
            ),
        }

    return {
        "requested_codes": codes,
        "found_count": len(items),
        "missing_codes": missing_codes,
        "failed_codes": failed_codes,
        "items": [_to_output(item) for item in items],
        "comparison": comparison,
    }
