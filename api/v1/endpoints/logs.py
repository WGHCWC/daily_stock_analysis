# -*- coding: utf-8 -*-
"""Operation log endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_operation_log_service
from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.logs import OperationLogItem, OperationLogListResponse
from src.services.operation_log_service import OperationLogService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "",
    response_model=OperationLogListResponse,
    responses={
        200: {"description": "操作日志列表"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取全局操作日志",
    description="返回最近的系统操作日志，可按分类或状态筛选。",
)
def get_operation_logs(
    limit: int = Query(100, ge=1, le=500, description="返回条数"),
    category: Optional[str] = Query(None, description="分类筛选"),
    status: Optional[str] = Query(None, description="状态筛选"),
    service: OperationLogService = Depends(get_operation_log_service),
) -> OperationLogListResponse:
    try:
        items = service.list_logs(limit=limit, category=category, status=status)
        return OperationLogListResponse(items=[OperationLogItem(**item) for item in items])
    except Exception as exc:
        logger.error("获取操作日志失败: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"获取操作日志失败: {str(exc)}"},
        )
