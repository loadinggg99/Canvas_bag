"""会话 checkpointer。

- RAM：InMemorySaver，进程重启后会话丢失，适合本地测试。
- Sqlite：SqliteSaver，把会话持久化到 data/db/checkpoint.db。
"""

import sqlite3
import threading
from contextlib import suppress
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

_sqlite_cache: dict[Path, SqliteSaver] = {}
_cache_lock = threading.Lock()


def _init_sqlite(db_path: Path) -> SqliteSaver:
    """返回（必要时创建）指定 SQLite 文件的 checkpointer。"""
    db_path = Path(db_path).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with _cache_lock:
        cached = _sqlite_cache.get(db_path)
        if cached is not None:
            return cached

        connection = sqlite3.connect(db_path, check_same_thread=False)
        checkpointer = SqliteSaver(connection)
        checkpointer.setup()  # 幂等：内部有 is_setup 标记
        _sqlite_cache[db_path] = checkpointer
        return checkpointer


def get_checkpointer(storage_mode: str, db_path: Path):
    """按存储模式返回 checkpointer。"""
    if storage_mode == "RAM":
        return InMemorySaver()

    if storage_mode == "Sqlite":
        return _init_sqlite(db_path)

    raise ValueError(
        f"未知的存储类型：{storage_mode!r}（可选 'RAM' / 'Sqlite'）"
    )


def close_checkpointers() -> None:
    """关闭并清空 SQLite 连接，测试或模拟进程重启时使用。"""
    with _cache_lock:
        while _sqlite_cache:
            _, checkpointer = _sqlite_cache.popitem()
            with suppress(Exception):
                checkpointer.conn.close()
