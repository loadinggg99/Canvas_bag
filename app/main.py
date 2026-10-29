# app/main.py —— FastAPI 应用入口
#
# 启动命令（在项目根目录执行）：
#   .venv/bin/python -m uvicorn app.main:app --reload
#
# 打开 http://127.0.0.1:8000/ 看前端，http://127.0.0.1:8000/docs 看接口文档。

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import agent, analytics, imports, products, simulations
from app.core import AppConfig, setup_logging

setup_logging()

app = FastAPI(
    title="Price_pilot_v1",
    version="0.1.0",
)

# CORS 默认允许所有来源，方便本地开发；
# 生产环境在 .env 里设置 CORS_ORIGINS=https://你的域名
cors_origins = [
    origin.strip()
    for origin in AppConfig().cors_origins.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["系统"])
def health():
    """健康检查（只表示进程还活着，不检查数据库）。"""
    return {"status": "ok"}


# 注册业务接口。顺序很重要：先注册 /api 路由，再挂静态文件，否则 /api 会被静态文件兜底拦截。
app.include_router(imports.router)
app.include_router(products.router)
app.include_router(analytics.router)
app.include_router(simulations.router)
app.include_router(agent.router)

# 挂载前端静态文件（放在最后，作为兜底；html=True 表示访问 "/" 返回 index.html）
frontend_dir = Path(__file__).resolve().parent / "frontend"
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
