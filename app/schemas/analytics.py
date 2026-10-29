# app/schemas/analytics.py —— 利润分析响应结构

from pydantic import BaseModel


class Anomaly(BaseModel):
    """一条异常提示。"""

    code: str
    severity: str
    message: str


class ProductAnalytics(BaseModel):
    """单个商品的分析结果。"""

    product_code: str
    pdd_sale_price: float
    pdd_profit: float
    profit_margin: float
    anomalies: list[Anomaly]


class AnalyticsSummary(BaseModel):
    """整表分析汇总，字段与 services 里 analytics_products 的返回一致。"""

    total: int
    sort_by: str
    items: list[ProductAnalytics]
