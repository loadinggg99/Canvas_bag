# app/api/simulations.py —— 定价模拟接口
#
# 路由是 async def；数据库查询和同步模拟计算放入线程池。

import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.core import to_decimal
from app.db import BosidengPrice, db_session
from app.schemas.simulation import SimulationRequest
from app.services import simulations

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["定价模拟"])


def _simulate_sync(req: SimulationRequest) -> dict | None:
    """同步查询商品并执行模拟，由线程池执行；找不到商品返回 None。"""
    with db_session() as db:
        product = db.get(BosidengPrice, req.product_code)

    if product is None:
        return None

    return simulations.simulate_price(
        product=product,
        target_price=to_decimal(req.target_price),
        target_margin=to_decimal(req.target_margin),
        min_price=to_decimal(req.min_price),
        max_price=to_decimal(req.max_price),
    )


@router.post("/simulations")
async def create_simulation(req: SimulationRequest):
    """给定新售价，调用 simulations.simulate_price 做定价模拟。"""
    try:
        result = await run_in_threadpool(_simulate_sync, req)
    except (TypeError, ValueError) as exc:
        # 这些是业务校验错误，可以把原因安全地返回给前端
        raise HTTPException(status_code=400, detail=str(exc))
    except SQLAlchemyError:
        logger.exception("查询商品失败，无法做定价模拟")
        raise HTTPException(status_code=503, detail="数据库暂不可用，请稍后重试")
    except Exception:
        logger.exception("定价模拟失败")
        raise HTTPException(status_code=500, detail="定价模拟失败，请稍后重试")

    if result is None:
        raise HTTPException(status_code=404, detail=f"找不到货号 {req.product_code}")

    return result
