# -*- coding: utf-8 -*-
"""Operation log service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.repositories.operation_log_repo import OperationLogRepository
from src.storage import DatabaseManager


class OperationLogService:
    """通用操作日志服务。"""

    def __init__(
        self,
        *,
        db_manager: Optional[DatabaseManager] = None,
        repo: Optional[OperationLogRepository] = None,
    ):
        self._db_manager = db_manager or DatabaseManager.get_instance()
        self._repo = repo or OperationLogRepository(db_manager=self._db_manager)

    def list_logs(
        self,
        *,
        limit: int = 100,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        rows = self._repo.list_recent(limit=limit, category=category, status=status)
        return [row.to_dict() for row in rows]

    def record(
        self,
        *,
        category: str,
        action: str,
        level: str = "info",
        status: str = "success",
        title: str,
        message: str,
        stock_code: Optional[str] = None,
        stock_name: Optional[str] = None,
        task_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        row = self._repo.create(
            category=category,
            action=action,
            level=level,
            status=status,
            title=title,
            message=message,
            stock_code=stock_code,
            stock_name=stock_name,
            task_id=task_id,
            details=details,
        )
        return row.to_dict()
