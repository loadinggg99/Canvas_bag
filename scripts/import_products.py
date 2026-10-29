# scripts/import_products.py —— 从命令行导入商品文件
#
# 运行：.venv/bin/python -m scripts.import_products
# 或：  .venv/bin/python -m scripts.import_products 另一个文件.xlsx

import argparse

from app.core import setup_logging
from app.services.import_service import write_to_db


def main() -> None:
    parser = argparse.ArgumentParser(description="把 data/raw/ 下的 Excel/CSV 导入 MySQL")
    parser.add_argument(
        "filename",
        nargs="?",
        default="波司登拼多多价格.xlsx",
        help="data/raw/ 目录下的文件名，默认：波司登拼多多价格.xlsx",
    )
    args = parser.parse_args()

    setup_logging()
    df = write_to_db(args.filename)
    print(f"导入完成：{args.filename}，共 {len(df)} 行")


if __name__ == "__main__":
    main()
