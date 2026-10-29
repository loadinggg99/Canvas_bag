# app/core/logging.py —— 统一日志配置

import logging


def setup_logging(level: int = logging.INFO) -> None:
    """给应用配置一个简单、统一的日志格式。

    uvicorn 等框架可能已经配置过日志，这里使用 basicConfig 的默认行为：
    已经有 root handler 时不会重复添加。
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    # HTTP 客户端和模型 SDK 的 INFO 日志会淹没业务日志
    for noisy_logger in ("httpx", "httpcore", "httpx2", "httpcore2", "openai"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)
