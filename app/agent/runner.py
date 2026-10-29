"""Agent 构建与调用入口。

对外只暴露三件事：
- build_agent()：创建 Agent（测试或特殊场景可指定 RAM / Sqlite）；
- get_agent()：延迟构建进程内单例；
- run_agent()：执行一轮对话，返回最终文本和本轮使用过的工具。

业务工具全部来自 app.agent.tools，数据访问和利润计算仍然在 services 层。
"""

import logging
import threading
import time
from typing import Literal

from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.messages import HumanMessage
from pydantic import ValidationError

from app.agent.checkpointer import get_checkpointer
from app.agent.llm import create_main_llm, create_summary_llm
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import (
    analyze_profit,
    check_pricing_risks,
    compare_products,
    query_products,
    simulate_price,
)
from app.core import get_agent_settings

logger = logging.getLogger(__name__)

StorageMode = Literal["RAM", "Sqlite"]

TOOLS = [
    query_products,
    analyze_profit,
    simulate_price,
    check_pricing_risks,
    compare_products,
]

_agent = None
_semaphore: threading.Semaphore | None = None
_agent_lock = threading.Lock()


class AgentConfigurationError(RuntimeError):
    """Agent 缺少必要配置，例如 DEEPSEEK_API_KEY。"""


def build_agent(storage_mode: StorageMode = "Sqlite"):
    """组装模型、工具、摘要中间件和 checkpointer。"""
    settings = get_agent_settings()

    main_llm = create_main_llm(settings)
    summary_llm = create_summary_llm(settings)
    checkpointer = get_checkpointer(storage_mode, settings.db_path)

    middleware = SummarizationMiddleware(
        model=summary_llm,
        trigger=("tokens", settings.summary_trigger_tokens),
        keep=("messages", settings.summary_keep_messages),
    )

    agent = create_agent(
        model=main_llm,
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        middleware=[middleware],
        checkpointer=checkpointer,
    )

    logger.info(
        "构建 agent：storage_mode=%s，工具 %d 个，主模型=%s，摘要模型=%s",
        storage_mode,
        len(TOOLS),
        settings.main_model,
        settings.summary_model,
    )
    return agent


def get_agent():
    """延迟构建 Agent 单例，避免 Web 服务启动时就调用大模型配置。"""
    global _agent, _semaphore

    if _agent is None:
        with _agent_lock:
            if _agent is None:
                try:
                    settings = get_agent_settings()
                except ValidationError as exc:
                    raise AgentConfigurationError(
                        "Agent 缺少 DEEPSEEK_API_KEY 等必要配置"
                    ) from exc

                logger.info("首次构建 agent（storage_mode=Sqlite）")
                _semaphore = threading.Semaphore(settings.max_concurrent_queries)
                _agent = build_agent(storage_mode="Sqlite")
                logger.info("agent 构建完成")

    return _agent


def _content_to_text(content: object) -> str:
    """把模型返回的 str / list content 统一转成字符串。"""
    if content is None:
        return ""

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(getattr(item, "text", item)))
        return "".join(parts).strip()

    return str(content).strip()


def _used_tool_names(messages: list) -> list[str]:
    """从本轮消息里收集实际调用过的工具名。"""
    names = set()
    for message in messages:
        for call in (getattr(message, "tool_calls", None) or []):
            if isinstance(call, dict):
                name = call.get("name")
            else:
                name = getattr(call, "name", None)
            if name:
                names.add(name)
    return sorted(names)


def _messages_since_last_human(messages: list) -> list:
    """只保留最后一轮用户输入之后的消息。

    checkpointer 会返回整个 thread 的历史，如果直接扫描全部消息，
    used_tools 会把前几轮调用过的工具也算进来。
    """
    start = 0
    for index, message in enumerate(messages):
        if isinstance(message, HumanMessage):
            start = index
    return messages[start:]


def run_agent(message: str, thread_id: str = "web") -> dict:
    """执行一轮 Agent 对话。

    thread_id 相同的请求共享历史会话；不同 thread_id 互不影响。
    """
    message = message.strip()
    if not message:
        raise ValueError("消息不能为空")

    agent = get_agent()
    semaphore = _semaphore or threading.Semaphore(1)

    started = time.perf_counter()
    logger.info("Agent 开始处理：thread_id=%s，输入 %d 字符", thread_id, len(message))

    with semaphore:
        waited = time.perf_counter() - started
        if waited > 0.5:
            logger.info("Agent 排队 %.2fs 后执行", waited)

        try:
            result = agent.invoke(
                {"messages": [HumanMessage(content=message)]},
                config={"configurable": {"thread_id": thread_id}},
            )
        except Exception:
            logger.exception("Agent 执行失败：thread_id=%s", thread_id)
            raise

    messages = result.get("messages", []) if isinstance(result, dict) else []
    if not messages:
        raise RuntimeError("Agent 没有返回消息")

    reply = _content_to_text(messages[-1].content)
    if not reply:
        raise RuntimeError("Agent 返回了空内容")

    used_tools = _used_tool_names(_messages_since_last_human(messages))

    logger.info(
        "Agent 完成：thread_id=%s，耗时 %.2fs，消息 %d 条，工具 %s，回复 %d 字符",
        thread_id,
        time.perf_counter() - started,
        len(messages),
        used_tools,
        len(reply),
    )

    return {
        "reply": reply,
        "thread_id": thread_id,
        "used_tools": used_tools,
    }
