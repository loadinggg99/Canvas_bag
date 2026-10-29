"""Agent 命令行交互入口。

用法（项目根目录）：
    .venv/bin/python -m app.agent.test

输入 exit / quit 退出。
"""

import sys
from pathlib import Path

if __package__ in (None, ""):
    # 支持直接运行：python app/agent/test.py
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.agent.runner import run_agent
from app.core import setup_logging


def main() -> None:
    setup_logging()
    print("Price_pilot Agent 已启动，输入 exit / quit 退出。\n")

    while True:
        try:
            message = input("你：")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if message.strip().lower() in ("exit", "quit"):
            break

        try:
            result = run_agent(message, thread_id="cli")
        except Exception as exc:
            print(f"Agent 调用失败：{type(exc).__name__}: {exc}\n")
            continue

        print(f"助手：{result['reply']}")
        if result["used_tools"]:
            print(f"（本轮工具：{', '.join(result['used_tools'])}）")
        print()


if __name__ == "__main__":
    main()
