# app/schemas/product.py —— 商品相关请求/响应结构

from pydantic import BaseModel


class ProductOut(BaseModel):
    """返回给前端的单个商品。金额用 float，方便前端直接显示。"""

    product_code: str        # 货号
    tag_price: float         # 吊牌价
    settlement_price: float  # 二级结算价
    fee: float               # 费用
    pdd_sale_price: float    # 拼多多出售价格
    pdd_gross_profit: float  # PDD 毛利
    agent_settlement_price: float  # 代理结算价格
    agent_discount: float    # 代理折扣
    agent_profit: float      # 代理利润
    own_profit: float        # 自己利润


class ProductListOut(BaseModel):
    """商品列表分页返回。"""

    total: int
    page: int
    page_size: int
    items: list[ProductOut]
