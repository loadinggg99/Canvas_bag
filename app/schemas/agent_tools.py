# app/schemas/agent_tools.py —— Agent 工具入参模型
#
# 这里只定义大模型调用工具时传入的参数结构，保持纯 Pydantic，
# 不导入 db、services 或 langchain，方便单独测试和复用。

# 外部库
from typing import Literal

from pydantic import BaseModel, Field


class QueryProductsInput(BaseModel):
    """商品查询参数。"""

    product_code: str | None = Field(
        default=None,
        description="货号，支持部分匹配，例如 B201；不填则查询全部商品",
    )
    min_profit: float | None = Field(
        default=None,
        description="最低 PDD 毛利（元），包含边界",
    )
    max_profit: float | None = Field(
        default=None,
        description="最高 PDD 毛利（元），包含边界",
    )
    min_sale_price: float | None = Field(
        default=None,
        description="最低拼多多售价（元），包含边界",
    )
    max_sale_price: float | None = Field(
        default=None,
        description="最高拼多多售价（元），包含边界",
    )
    sort_by: Literal["pdd_profit", "profit_margin", "pdd_sale_price"] = Field(
        default="pdd_profit",
        description="排序字段：pdd_profit=毛利，profit_margin=毛利率，pdd_sale_price=售价",
    )
    descending: bool = Field(
        default=True,
        description="是否降序：True 从大到小，False 从小到大",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="最多返回多少条商品记录，范围 1~50",
    )


class SimulatePriceInput(BaseModel):
    """定价模拟参数。"""

    product_code: str = Field(
        description="要模拟的商品货号，例如 B20112320",
    )
    target_price: float = Field(
        gt=0,
        description="目标售价（元），必须大于 0",
    )


class CheckPricingRisksInput(BaseModel):
    """定价风险检查参数。"""

    product_code: str | None = Field(
        default=None,
        description="只检查某个货号，支持部分匹配；不填则检查全部商品",
    )
    margin_threshold: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description=(
            "毛利率风险阈值，0~1 的小数；低于它记为低毛利风险。"
            "不填时使用服务层默认阈值（当前为 5%）"
        ),
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="最多返回多少条有风险的商品，范围 1~100",
    )


class CompareProductsInput(BaseModel):
    """商品对比参数。"""

    product_codes: list[str] = Field(
        min_length=2,
        max_length=10,
        description="要对比的货号列表，至少 2 个、最多 10 个",
    )
