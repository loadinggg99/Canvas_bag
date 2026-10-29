# app/db/session.py —— 数据库连接、Session

# 外部库
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import sessionmaker

# 内部库
from app.core import MySQLConfig


def get_mysql_engine():
    """根据配置创建 MySQL 引擎。

    使用 URL.create 而不是手写连接字符串：
    - 密码里有 @、/ 等特殊字符时也能正确转义；
    - 日志里不会直接拼接出带密码的连接串。
    """
    mysql_config = MySQLConfig()

    url = URL.create(
        "mysql+pymysql",
        username=mysql_config.username,
        password=mysql_config.password,
        host=mysql_config.host,
        port=mysql_config.port,
        database=mysql_config.database,
        query={"charset": mysql_config.charset},
    )

    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


# 全项目共用一个引擎，避免每个模块各建一套连接池
mysql_engine = get_mysql_engine()

db_session = sessionmaker(
    bind=mysql_engine,
    autoflush=False,   # 查询前不自动把未提交修改发给数据库
    autocommit=False,  # 只有 commit 后才真正提交
)
