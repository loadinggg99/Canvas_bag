# app/api/products.py —— 商品查询接口
#
# 这里直接通过 db 层的 db_session 查询 BosidengPrice，不依赖 services。

import logging

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.core import obj_to_dict
from app.db import BosidengPrice, db_session
from app.schemas.product import ProductListOut, ProductOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["商品"])


@router.get("/products", response_model=ProductListOut)
def list_products(
    search: str | None = Query(default=None, description="按货号模糊搜索"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """分页查询商品，支持按货号模糊搜索。"""
    count_stmt = select(func.count()).select_from(BosidengPrice)
    stmt = select(BosidengPrice)

    if search:
        pattern = f"%{search}%"  # SQL LIKE 通配符：匹配任意长度字符
        count_stmt = count_stmt.where(BosidengPrice.product_code.like(pattern))
        stmt = stmt.where(BosidengPrice.product_code.like(pattern))

    try:
        with db_session() as db:
            total = db.scalar(count_stmt) or 0
            rows = db.scalars(
                stmt.order_by(BosidengPrice.product_code)
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            items = [obj_to_dict(p) for p in rows]
    except SQLAlchemyError:
        logger.exception("查询商品列表失败")
        raise HTTPException(status_code=503, detail="数据库暂不可用，请稍后重试")

    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/products/{product_code}", response_model=ProductOut)
def get_product(product_code: str):
    """按货号查询单个商品。"""
    try:
        with db_session() as db:
            product = db.get(BosidengPrice, product_code)
    except SQLAlchemyError:
        logger.exception("查询商品失败：%s", product_code)
        raise HTTPException(status_code=503, detail="数据库暂不可用，请稍后重试")

    if product is None:
        raise HTTPException(status_code=404, detail=f"找不到货号 {product_code}")
    return obj_to_dict(product)
