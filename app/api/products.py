# app/api/products.py —— 商品查询接口
#
# 路由使用 async def；SQLAlchemy 是同步库，所以实际数据库操作放到
# run_in_threadpool 中执行，避免阻塞 FastAPI 的事件循环。

import logging

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.core import obj_to_dict
from app.db import BosidengPrice, db_session
from app.schemas.product import ProductListOut, ProductOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["商品"])


def _list_products_sync(
    search: str | None,
    page: int,
    page_size: int,
) -> dict:
    """同步数据库查询，由线程池执行。"""
    count_stmt = select(func.count()).select_from(BosidengPrice)
    stmt = select(BosidengPrice)

    if search:
        pattern = f"%{search}%"  # SQL LIKE 通配符：匹配任意长度字符
        count_stmt = count_stmt.where(BosidengPrice.product_code.like(pattern))
        stmt = stmt.where(BosidengPrice.product_code.like(pattern))

    with db_session() as db:
        total = db.scalar(count_stmt) or 0
        rows = db.scalars(
            stmt.order_by(BosidengPrice.product_code)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        items = [obj_to_dict(p) for p in rows]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


@router.get("/products", response_model=ProductListOut)
async def list_products(
    search: str | None = Query(default=None, description="按货号模糊搜索"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """分页查询商品，支持按货号模糊搜索。"""
    try:
        return await run_in_threadpool(
            _list_products_sync,
            search,
            page,
            page_size,
        )
    except SQLAlchemyError:
        logger.exception("查询商品列表失败")
        raise HTTPException(status_code=503, detail="数据库暂不可用，请稍后重试")


def _get_product_sync(product_code: str) -> dict | None:
    """同步查询单个商品，由线程池执行。"""
    with db_session() as db:
        product = db.get(BosidengPrice, product_code)
        if product is None:
            return None
        return obj_to_dict(product)


@router.get("/products/{product_code}", response_model=ProductOut)
async def get_product(product_code: str):
    """按货号查询单个商品。"""
    try:
        product = await run_in_threadpool(_get_product_sync, product_code)
    except SQLAlchemyError:
        logger.exception("查询商品失败：%s", product_code)
        raise HTTPException(status_code=503, detail="数据库暂不可用，请稍后重试")

    if product is None:
        raise HTTPException(status_code=404, detail=f"找不到货号 {product_code}")
    return product
