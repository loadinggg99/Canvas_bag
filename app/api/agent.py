# app/api/agent.py —— Agent 对话接口
#
# 路由是 async def；Agent 和 LangGraph 是同步调用，放入线程池执行，
# 这样模型思考期间不会阻塞 FastAPI 事件循环。

import logging

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from app.agent.runner import AgentConfigurationError, run_agent
from app.schemas.agent import AgentChatRequest, AgentChatResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["Agent"])


@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(req: AgentChatRequest):
    """把用户消息交给 Agent，返回本轮最终回答。"""
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="消息不能为空")

    try:
        return await run_in_threadpool(run_agent, message, req.thread_id)
    except AgentConfigurationError:
        logger.exception("Agent 配置缺失")
        raise HTTPException(
            status_code=503,
            detail="Agent 未配置，请检查 .env 中的 DEEPSEEK_API_KEY",
        )
    except ValueError as exc:
        # 参数类错误可以安全返回给调用方
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("Agent 对话失败")
        raise HTTPException(status_code=500, detail="Agent 暂时不可用，请稍后重试")
