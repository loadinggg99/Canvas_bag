"""LLM 实例工厂。

主模型负责对话和工具调用；摘要模型只负责长对话压缩。
配置从 app.core.AgentConfig 读取，不在代码里写死密钥。
"""

from langchain_openai import ChatOpenAI

from app.core import AgentConfig


def create_main_llm(settings: AgentConfig) -> ChatOpenAI:
    """创建主对话模型（支持工具调用）。"""
    return ChatOpenAI(
        model=settings.main_model,
        api_key=settings.api_key,
        base_url=settings.base_url,
        temperature=0.2,
        timeout=60,
        max_retries=2,
    )


def create_summary_llm(settings: AgentConfig) -> ChatOpenAI:
    """创建摘要模型，用于历史对话过长时压缩上下文。"""
    return ChatOpenAI(
        model=settings.summary_model,
        api_key=settings.summary_model_api_key,
        base_url=settings.summary_model_base_url,
        temperature=0.3,
        timeout=60,
        max_retries=2,
    )
