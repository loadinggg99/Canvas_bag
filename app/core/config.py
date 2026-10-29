# app/core/config.py —— 环境变量、配置
#
# 所有敏感配置都从环境变量或 .env 读取，代码里不保存密码和 API Key。

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

TABLE_DIR = Path(__file__).resolve().parent.parent.parent / "data"
ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"
DB_DIR = TABLE_DIR / "db"


class MySQLConfig(BaseSettings):
    """MySQL 连接配置，从 MYSQL_* 环境变量或 .env 读取。"""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        env_prefix="MYSQL_",
        extra="ignore",
    )

    host: str = Field(default="127.0.0.1", frozen=True, description="主机")
    port: int = Field(default=3306, frozen=True, description="端口")
    username: str = Field(frozen=True, description="用户")
    password: str = Field(frozen=True, description="密码")
    database: str = Field(description="数据库")
    charset: str = Field(default="utf8mb4", description="字符集")


class TableSettings(BaseModel):
    """数据文件所在目录：当前 Excel 直接放在 data/ 下。"""

    table_path: Path = TABLE_DIR


class AgentConfig(BaseSettings):
    """大模型配置。只有真正创建 Agent 时才调用 get_agent_settings()。"""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    main_model: str = "deepseek-flash"
    structured_model: str = "deepseek-chat"  # 非思考模型
    api_key: str = Field(alias="DEEPSEEK_API_KEY")
    base_url: str = "https://api.deepseek.com"

    summary_model: str = "deepseek-flash"
    summary_model_api_key: str = Field(alias="DEEPSEEK_API_KEY")
    summary_model_base_url: str = "https://api.deepseek.com"
    summary_trigger_tokens: int = 8192
    summary_keep_messages: int = 8

    # 同时执行的 Agent 查询上限，超出的请求在进程内排队
    max_concurrent_queries: int = Field(default=3, ge=1, le=20)

    db_path: Path = DB_DIR / "checkpoint.db"


class AppConfig(BaseSettings):
    """Web 应用本身的基础配置。"""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    cors_origins: str = "*"


@lru_cache
def get_agent_settings() -> AgentConfig:
    """延迟创建 Agent 配置，避免普通接口在导入时就要求 API Key。"""
    return AgentConfig()
