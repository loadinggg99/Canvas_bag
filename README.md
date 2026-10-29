## 各个目录负责什么？
|目录|主要职责|你可以怎么理解|
|---|---|---|
|`models/`|数据库表结构|数据在数据库里怎么存|
|`schemas/`|请求和响应格式|API 接收什么、返回什么|
|`api/`|HTTP接口|接收前端请求|
|`services/`|业务逻辑|真正执行查询、计算和导入|
|`agent/`|大模型与工具调用|决定调用哪个业务工具|
|`db/`|数据库连接|负责连接 SQLite|
|`tests/`|自动化测试|验证代码是否正确|

特别注意：models/product.py 和 schemas/product.py 不是重复文件。
- models/product.py 定义 SQLAlchemy 数据库模型。
- schemas/product.py 定义 Pydantic 请求、响应模型。

开发顺序
建议不要一次创建所有文件，可以按下面的顺序逐步搭建：
1. db/、models/：先让数据库运行起来。
2. services/import_service.py、api/imports.py：把 Excel 导入数据库。
3. services/product_service.py、api/products.py：实现商品查询。
4. services/analytics_service.py、api/analytics.py：完成利润排序与公式核验。
5. services/pricing_service.py、api/simulations.py：实现定价模拟。
6. agent/tools.py、agent/runner.py、api/agent.py：最后接入大模型。
7. frontend/、tests/、README.md：完成展示和验收。
第一阶段暂时不用创建复杂的多 Agent 结构、向量数据库或独立的消息队列。等这个目录里的核心流程跑通后，再考虑引入 LangGraph。
