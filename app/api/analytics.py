# app/api/analytics.py —— 利润分析接口
#
# 路由是 async def；同步 SQLAlchemy 查询和利润计算放入线程池。

import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.db import BosidengPrice, db_session
from app.schemas.analytics import AnalyticsSummary
from app.services import analytics_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["分析"])


def _get_analytics_sync() -> dict:
    """同步查询全部商品并计算利润，由线程池执行。"""
    with db_session() as db:
        products = db.scalars(select(BosidengPrice)).all()

    return analytics_service.analytics_products(products)


@router.get("/analytics", response_model=AnalyticsSummary)
async def get_analytics():
    """对整张表做利润分析：调用 analytics_service.analytics_products。"""
    try:
        return await run_in_threadpool(_get_analytics_sync)
    except SQLAlchemyError:
        logger.exception("查询商品失败，无法做利润分析")
        raise HTTPException(status_code=503, detail="数据库暂不可用，请稍后重试")
    except Exception:
        logger.exception("利润分析失败")
        raise HTTPException(status_code=500, detail="利润分析失败，请稍后重试")
