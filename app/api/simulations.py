# app/api/simulations.py —— 定价模拟接口

import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.core import to_decimal
from app.db import BosidengPrice, db_session
from app.schemas.simulation import SimulationRequest
from app.services import simulations

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["定价模拟"])


@router.post("/simulations")
def create_simulation(req: SimulationRequest):
    """给定新售价，调用 simulations.simulate_price 做定价模拟。"""
    try:
        with db_session() as db:
            product = db.get(BosidengPrice, req.product_code)
    except SQLAlchemyError:
        logger.exception("查询商品失败，无法做定价模拟")
        raise HTTPException(status_code=503, detail="数据库暂不可用，请稍后重试")

    if product is None:
        raise HTTPException(status_code=404, detail=f"找不到货号 {req.product_code}")

    try:
        return simulations.simulate_price(
            product=product,
            target_price=to_decimal(req.target_price),
            target_margin=to_decimal(req.target_margin),
            min_price=to_decimal(req.min_price),
            max_price=to_decimal(req.max_price),
        )
    except (TypeError, ValueError) as exc:
        # 这些是业务校验错误，可以把原因安全地返回给前端
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("定价模拟失败")
        raise HTTPException(status_code=500, detail="定价模拟失败，请稍后重试")
