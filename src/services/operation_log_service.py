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
        page: int = 1,
        page_size: int = 20,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        safe_page_size = max(1, min(page_size, 20))
        total = self._repo.count_recent(category=category, status=status)
        total_pages = max(1, (total + safe_page_size - 1) // safe_page_size) if total > 0 else 1
        safe_page = min(max(1, page), total_pages)
        offset = (safe_page - 1) * safe_page_size
        rows = self._repo.list_recent(
            limit=safe_page_size,
            offset=offset,
            category=category,
            status=status,
        )
        return {
            "items": [row.to_dict() for row in rows],
            "total": total,
            "page": safe_page,
            "page_size": safe_page_size,
            "total_pages": total_pages,
        }

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
