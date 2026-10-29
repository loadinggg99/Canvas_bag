# app/services/import_service.py —— 把 Excel/CSV 安全地导入数据库
#
# 导入策略：
# 1. 先校验文件和列，避免坏文件进入数据库；
# 2. 数据先写入临时表；
# 3. 临时表写完后，再用一次原子 RENAME 换成正式表。
#
# 这样即使读取或写入失败，原来的 test_price 也不会被提前删掉。

# 外部库
import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import MetaData, inspect, text
from sqlalchemy.exc import SQLAlchemyError

# 内部库
from app.core import TableSettings
from app.db import BosidengPrice, mysql_engine

logger = logging.getLogger(__name__)

table_settings = TableSettings()

TABLE_NAME = BosidengPrice.__tablename__
STAGING_TABLE_NAME = f"{TABLE_NAME}_import"
BACKUP_TABLE_NAME = f"{TABLE_NAME}_old"
REQUIRED_COLUMNS = [column.name for column in BosidengPrice.__table__.columns]
SUPPORTED_SUFFIXES = {".xlsx", ".xls", ".csv"}


def _safe_file_path(filename: str) -> Path:
    """只允许读取 data/ 目录下的文件，防止 ../ 路径穿越。"""
    base_dir = table_settings.table_path.resolve()
    file_path = (base_dir / filename).resolve()

    if file_path.parent != base_dir:
        raise ValueError("文件名不合法，只能导入 data 目录下的文件")

    if not file_path.is_file():
        raise FileNotFoundError(f"找不到文件：{filename}")

    return file_path


def _read_file(file_path: Path) -> pd.DataFrame:
    """按扩展名读取 Excel 或 CSV。"""
    suffix = file_path.suffix.lower()

    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"不支持的文件类型：{file_path.suffix}")

    if suffix == ".csv":
        try:
            # utf-8-sig 可以兼容 Excel 导出的带 BOM 的 CSV
            return pd.read_csv(file_path, encoding="utf-8-sig")
        except UnicodeDecodeError:
            return pd.read_csv(file_path, encoding="gbk")

    try:
        return pd.read_excel(file_path)
    except ImportError as exc:
        # .xls 需要额外的 xlrd 依赖，给出比“导入失败”更明确的信息
        raise ValueError("读取 .xls 文件需要先安装 xlrd") from exc


def _validate_dataframe(df: pd.DataFrame) -> None:
    """在碰数据库之前，把最常见的坏数据问题检查出来。"""
    df.columns = [str(column).strip() for column in df.columns]

    missing_columns = [
        column for column in REQUIRED_COLUMNS if column not in df.columns
    ]
    if missing_columns:
        raise ValueError(f"文件缺少列：{', '.join(missing_columns)}")

    extra_columns = [
        column for column in df.columns if column not in REQUIRED_COLUMNS
    ]
    if extra_columns:
        raise ValueError(f"文件存在未知列：{', '.join(extra_columns)}")

    if df.empty:
        raise ValueError("文件里没有数据")

    if df["货号"].isna().any():
        raise ValueError("货号存在空值")

    # 货号统一去掉首尾空格，避免同一个货号出现两个版本
    df["货号"] = df["货号"].astype(str).str.strip()

    if df["货号"].duplicated().any():
        duplicated = df.loc[df["货号"].duplicated(), "货号"].head(5).tolist()
        raise ValueError(f"货号重复，例如：{', '.join(duplicated)}")

    too_long = df["货号"].str.len() > 50
    if too_long.any():
        raise ValueError("存在超过 50 个字符的货号")

    # 金额列必须是数字，否则写数据库时才报错就太晚了
    for column in REQUIRED_COLUMNS[1:]:
        try:
            df[column] = pd.to_numeric(df[column], errors="raise")
        except (TypeError, ValueError) as exc:
            raise ValueError(f"列「{column}」包含非数字内容") from exc

    null_columns = [
        column for column in REQUIRED_COLUMNS if df[column].isna().any()
    ]
    if null_columns:
        raise ValueError(f"这些列存在空值：{', '.join(null_columns)}")


def _replace_table(df: pd.DataFrame) -> None:
    """把校验后的数据写入临时表，再原子替换正式表。"""
    table = BosidengPrice.__table__
    staging_table = table.to_metadata(MetaData(), name=STAGING_TABLE_NAME)

    # 清理上一次失败留下的临时表
    staging_table.drop(bind=mysql_engine, checkfirst=True)
    staging_table.create(bind=mysql_engine)

    try:
        df.to_sql(
            name=STAGING_TABLE_NAME,
            con=mysql_engine,
            if_exists="append",
            index=False,
        )
    except Exception:
        # 临时表失败不影响正式表
        staging_table.drop(bind=mysql_engine, checkfirst=True)
        logger.exception("写入临时表失败，原表未改动")
        raise

    old_table_exists = inspect(mysql_engine).has_table(TABLE_NAME)

    with mysql_engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS `{BACKUP_TABLE_NAME}`"))

        if old_table_exists:
            # MySQL 的 RENAME TABLE 可以一次原子替换两张表
            conn.execute(text(
                f"RENAME TABLE `{TABLE_NAME}` TO `{BACKUP_TABLE_NAME}`, "
                f"`{STAGING_TABLE_NAME}` TO `{TABLE_NAME}`"
            ))
        else:
            conn.execute(text(
                f"RENAME TABLE `{STAGING_TABLE_NAME}` TO `{TABLE_NAME}`"
            ))

    # 新表已经生效，旧表清理失败只记录警告，不让用户误以为导入失败
    try:
        with mysql_engine.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS `{BACKUP_TABLE_NAME}`"))
    except SQLAlchemyError:
        logger.warning("新表已切换，但旧表备份 %s 清理失败", BACKUP_TABLE_NAME)


def write_to_db(table_name: str = "波司登拼多多价格.xlsx") -> pd.DataFrame:
    """读取 data/ 下的文件，校验后安全替换 test_price 表。"""
    file_path = _safe_file_path(table_name)

    try:
        df = _read_file(file_path)
        _validate_dataframe(df)
        _replace_table(df)
    except SQLAlchemyError:
        logger.exception("导入数据库失败：%s", file_path.name)
        raise
    except Exception:
        logger.exception("导入文件失败：%s", file_path.name)
        raise

    logger.info("已导入 %s -> 表 %s，共 %s 行", file_path.name, TABLE_NAME, len(df))
    return df


if __name__ == "__main__":
    from app.core import setup_logging

    setup_logging()
    write_to_db()
