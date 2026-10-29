# app/schemas/import_task.py —— 数据导入相关请求/响应结构

from pydantic import BaseModel


class ImportRequest(BaseModel):
    """导入请求：指定 data/raw 目录下的文件名。"""

    filename: str = "波司登拼多多价格.xlsx"


class ImportResult(BaseModel):
    """导入结果。"""

    filename: str
    table_name: str
    imported_rows: int


class FileItem(BaseModel):
    """data/raw 目录里的一个可用数据文件。"""

    filename: str
    size_bytes: int
