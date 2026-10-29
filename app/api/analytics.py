# app/api/analytics.py —— 利润分析接口

import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db import BosidengPrice, db_session
from app.schemas.analytics import AnalyticsSummary
from app.services import analytics_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["分析"])


@router.get("/analytics", response_model=AnalyticsSummary)
def get_analytics():
    """对整张表做利润分析：调用 analytics_service.analytics_products。"""
    try:
        with db_session() as db:
            products = db.scalars(select(BosidengPrice)).all()
    except SQLAlchemyError:
        logger.exception("查询商品失败，无法做利润分析")
        raise HTTPException(status_code=503, detail="数据库暂不可用，请稍后重试")

    try:
        return analytics_service.analytics_products(products)
    except Exception:
        logger.exception("利润分析失败")
        raise HTTPException(status_code=500, detail="利润分析失败，请稍后重试")
