# scripts/init_db.py —— 初始化数据库表
#
# 运行：.venv/bin/python -m scripts.init_db

from app.core import setup_logging
from app.db import Base, mysql_engine


def main() -> None:
    setup_logging()
    Base.metadata.create_all(bind=mysql_engine)
    print("数据库表已创建或已存在")


if __name__ == "__main__":
    main()
