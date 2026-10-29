"""Price_pilot_v1 本地启动入口。

用法（项目根目录）：
    .venv/bin/python main.py
    .venv/bin/python main.py --reload
    .venv/bin/python main.py --host 0.0.0.0 --port 8000
"""

import argparse
import socket

import uvicorn

from app.core import setup_logging


def check_port(host: str, port: int) -> None:
    """端口被占用时给出比 uvicorn 原始报错更明确的中文提示。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError as exc:
            raise SystemExit(
                f"端口 {port} 已被占用。请关闭旧服务，"
                f"或改用：.venv/bin/python main.py --port {port + 1}"
            ) from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="启动 Price_pilot_v1 Web 服务")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--port", type=int, default=8000, help="监听端口")
    parser.add_argument("--reload", action="store_true", help="开发模式：代码变更自动重载")
    args = parser.parse_args()

    check_port(args.host, args.port)
    setup_logging()
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
