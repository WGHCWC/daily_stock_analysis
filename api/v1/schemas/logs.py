# -*- coding: utf-8 -*-
"""Operation log schemas."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class OperationLogItem(BaseModel):
    """单条操作日志。"""

    id: int = Field(..., description="日志 ID")
    category: str = Field(..., description="日志分类")
    action: str = Field(..., description="操作类型")
    level: str = Field(..., description="日志级别")
    status: str = Field(..., description="操作状态")
    title: str = Field(..., description="日志标题")
    message: str = Field(..., description="日志内容")
    stock_code: Optional[str] = Field(None, description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    task_id: Optional[str] = Field(None, description="关联任务 ID")
    details: Optional[Dict[str, Any]] = Field(None, description="结构化明细")
    created_at: Optional[str] = Field(None, description="创建时间")


class OperationLogListResponse(BaseModel):
    """操作日志列表响应。"""

    items: List[OperationLogItem] = Field(default_factory=list, description="日志列表")
    total: int = Field(0, description="符合筛选条件的总记录数")
    page: int = Field(1, description="当前页码")
    page_size: int = Field(20, description="每页条数")
    total_pages: int = Field(1, description="总页数")
