# app/schemas/simulation.py —— 定价模拟请求结构

from pydantic import BaseModel, Field


class SimulationRequest(BaseModel):
    """定价模拟请求。target_price 必填，其余可选。"""

    product_code: str = Field(min_length=1, max_length=50)
    target_price: float = Field(gt=0, description="目标售价必须大于 0")
    target_margin: float | None = Field(
        default=None,
        ge=0,
        lt=1,
        description="目标毛利率，0~1 之间，不含 1",
    )
    min_price: float | None = Field(
        default=None,
        gt=0,
        description="允许的最低售价",
    )
    max_price: float | None = Field(
        default=None,
        gt=0,
        description="允许的最高售价",
    )
