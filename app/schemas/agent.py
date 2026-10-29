# app/schemas/agent.py —— Agent 对话接口的请求/响应结构

from uuid import uuid4

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    """一轮 Agent 对话请求。"""

    message: str = Field(
        min_length=1,
        max_length=4000,
        description="用户输入，会作为 HumanMessage 交给 Agent",
    )
    thread_id: str = Field(
        default_factory=lambda: str(uuid4()),
        min_length=1,
        max_length=100,
        description="会话 id；不传时自动生成，后续请求带上响应里的 id 即可续聊",
    )


class AgentChatResponse(BaseModel):
    """一轮 Agent 对话响应。"""

    reply: str = Field(description="Agent 的最终中文回答")
    thread_id: str = Field(description="本轮使用的会话 id")
    used_tools: list[str] = Field(
        default_factory=list,
        description="本轮实际调用过的工具名",
    )
