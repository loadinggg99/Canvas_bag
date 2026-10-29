# app/db/base.py SQLAlchemy Base


# 外部库
from decimal import Decimal
from sqlalchemy import String, Numeric
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

# 定义ORM模型
class BosidengPrice(Base):
    __tablename__ = "test_price"

    # 货号在 Excel 中没有重复，可以暂时作为 ORM 主键
    product_code: Mapped[str] = mapped_column(
        "货号",String(50),primary_key=True
    )

    # Decimal 是 Python 标准库 decimal 提供的十进制数值类型
    # Numeric(x,y) 是 SQLAlchemy 用来定义数据库列的数据类型，x表示整数位加小数位共x位，y表示小数点后保留y位
    tag_price: Mapped[Decimal] = mapped_column(
        "吊牌价",Numeric(10,2)
    )

    settlement_price: Mapped[Decimal] = mapped_column(
        "二级结算价",Numeric(10,2)
    )

    fee: Mapped[Decimal] = mapped_column(
        "费用",Numeric(10,2)
    )

    pdd_sale_price: Mapped[Decimal] = mapped_column(
        "拼多多出售价格", Numeric(10, 2)
    )

    pdd_gross_profit: Mapped[Decimal] = mapped_column(
        "PDD毛利", Numeric(10, 2)
    )

    agent_settlement_price: Mapped[Decimal] = mapped_column(
        "代理结算价格", Numeric(10, 2)
    )

    agent_discount: Mapped[Decimal] = mapped_column(
        "代理折扣", Numeric(10, 6)
    )

    agent_profit: Mapped[Decimal] = mapped_column(
        "代理利润", Numeric(10, 2)
    )

    own_profit: Mapped[Decimal] = mapped_column(
        "自己利润", Numeric(10, 2)
    )
