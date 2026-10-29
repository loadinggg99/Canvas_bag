# app/api/imports.py —— 数据导入接口

import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.core import TableSettings
from app.db import BosidengPrice
from app.schemas.import_task import FileItem, ImportRequest, ImportResult
from app.services import import_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["导入"])

# 可导入的文件后缀
SUPPORTED_SUFFIXES = {".xlsx", ".xls", ".csv"}


@router.get("/files", response_model=list[FileItem])
def list_files():
    """列出 data/raw 目录下可导入的数据文件。"""
    table_dir = TableSettings().table_path

    if not table_dir.is_dir():
        raise HTTPException(status_code=500, detail="数据目录不存在")

    files = []
    for path in sorted(table_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            files.append(FileItem(filename=path.name, size_bytes=path.stat().st_size))
    return files


@router.post("/import", response_model=ImportResult)
def import_data(req: ImportRequest):
    """把 data/raw 目录下的文件导入数据库（调用 import_service.write_to_db）。"""
    try:
        df = import_service.write_to_db(req.filename)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        # 文件名不合法、列缺失、空数据等可以安全返回给前端
        raise HTTPException(status_code=400, detail=str(exc))
    except SQLAlchemyError:
        logger.exception("导入失败：数据库错误")
        raise HTTPException(status_code=500, detail="导入失败，数据库错误")
    except Exception:
        logger.exception("导入失败：未知错误")
        raise HTTPException(status_code=500, detail="导入失败，请检查文件格式")

    return ImportResult(
        filename=req.filename,
        table_name=BosidengPrice.__tablename__,
        imported_rows=len(df),
    )
