# Price_pilot_v1

波司登拼多多价格导入、商品查询、利润分析和定价模拟的练习项目。后端使用 FastAPI + SQLAlchemy + MySQL，Agent 工具使用 LangChain。

## 目录职责

| 目录 | 职责 |
|---|---|
| `main.py` | 本地启动入口：`python main.py` |
| `app/api/` | HTTP 接口，接收前端请求 |
| `app/services/` | 业务逻辑：导入、利润计算、统计、模拟 |
| `app/db/` | MySQL 引擎、Session 和 ORM 模型 |
| `app/schemas/` | Pydantic 请求/响应模型、Agent 工具入参 |
| `app/core/` | 配置、类型转换、日志 |
| `app/agent/` | LangChain Agent：模型、提示词、工具和会话记忆 |
| `app/frontend/` | 静态页面 |
| `scripts/` | 初始化数据库、命令行导入 |
| `tests/` | 不需要数据库的核心逻辑测试 |

## 快速开始

1. 准备环境配置：

```bash
cp .env.example .env
# 然后编辑 .env，填入 MySQL 和大模型配置
```

2. 安装依赖：

```bash
uv sync
```

3. 初始化数据库表：

```bash
.venv/bin/python -m scripts.init_db
```

4. 导入 Excel 数据（文件放在 `data/raw/`）：

```bash
.venv/bin/python -m scripts.import_products
# 或指定文件名
.venv/bin/python -m scripts.import_products 另一个文件.xlsx
```

5. 启动 Web 服务：

```bash
.venv/bin/python main.py
```

开发时自动重载：

```bash
.venv/bin/python main.py --reload
```

也可以直接使用 uvicorn：

```bash
.venv/bin/python -m uvicorn app.main:app --reload
```

如果提示 `address already in use`，说明 8000 端口被旧服务占用：

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
kill <占用端口的PID>
```

或者直接换端口：

```bash
.venv/bin/python main.py --port 8001
```

- 页面：http://127.0.0.1:8000/
- 接口文档：http://127.0.0.1:8000/docs

## Agent 使用

Agent 已接入 5 个只读工具，支持按 `thread_id` 保存多轮会话。

接口：

```bash
curl -X POST http://127.0.0.1:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"查询 B20112320 的毛利率","thread_id":"demo"}'
```

响应包含：

- `reply`：最终中文回答
- `thread_id`：本轮会话 id
- `used_tools`：本轮实际调用过的工具名

也可以直接用命令行测试：

```bash
.venv/bin/python -m app.agent.test
```

Agent 结构：

- `app/agent/llm.py`：主模型和摘要模型
- `app/agent/prompts.py`：系统提示词
- `app/agent/tools.py`：5 个业务工具
- `app/agent/checkpointer.py`：SQLite 会话存储
- `app/agent/runner.py`：组装 Agent、并发控制、调用入口
- `app/api/agent.py`：`POST /api/agent/chat`
- 页面右下角“AI 对话”按钮：打开侧边栏，与同一 Agent 多轮对话

Agent 相关配置（都有默认值，按需覆盖）：

- `DEEPSEEK_API_KEY`：必填
- `MAIN_MODEL`：默认 `deepseek-flash`
- `SUMMARY_MODEL`：默认 `deepseek-flash`
- `MAX_CONCURRENT_QUERIES`：默认 3

## 测试

```bash
.venv/bin/python -m unittest discover -s tests -v
```

测试不连接数据库，主要覆盖 Decimal 转换、利润公式、排序、异常检测和 Agent 请求结构。

Agent 的端到端调用需要 `.env` 中的 `DEEPSEEK_API_KEY`。

## 重要业务口径

当前利润公式在 `app/services/analytics_service.py`：

```text
PDD 毛利 = 拼多多售价 - 二级结算价 - 费用 - 10
毛利率 = PDD 毛利 / 拼多多售价
```

其中固定扣减 `10` 元在代码里标为“暂定规则”，需要业务确认。

另外，数据库里的 `PDD毛利` 字段有 294/308 条比 Python 公式结果高 `0.01`（源表金额存在半分位，入库时按两位小数舍入）。当前分析、模拟和 Agent 工具统一使用 Python 公式结果；如果业务要以数据库字段为准，需要统一修改口径。

## 导入安全说明

导入不再先删除正式表，而是：

1. 校验文件路径、列名、空值、重复货号和数字类型；
2. 写入临时表 `test_price_import`；
3. 用 MySQL 原子 `RENAME TABLE` 替换 `test_price`；
4. 替换成功后再清理旧表。

所以文件或写入失败时，原表不会被提前删掉。

## 生产部署前还需要注意

- `.env` 不要提交，生产环境通过环境变量注入密钥；
- 把 `CORS_ORIGINS` 改成真实前端域名；
- 使用最小权限的 MySQL 账号；
- 在外层配置 HTTPS、反向代理、进程守护和日志收集；
- 表结构变更目前没有迁移工具，正式环境建议引入 Alembic；
- Agent 接口目前没有鉴权，生产环境需要网关鉴权或 API Key；
- Agent 使用进程内单例和 SQLite 会话存储，多进程部署时需要改成共享存储；
- `/api/agent/chat` 还没有接入前端页面。
