# -*- coding: utf-8 -*-
"""Persistent operation log repository."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, select

from src.storage import DatabaseManager, OperationLog


class OperationLogRepository:
    """操作日志仓储。"""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self._db_manager = db_manager

    @property
    def db(self) -> DatabaseManager:
        db_manager = self._db_manager
        if db_manager is None or not getattr(db_manager, "_initialized", False):
            db_manager = DatabaseManager.get_instance()
            self._db_manager = db_manager
        return db_manager

    def create(
        self,
        *,
        category: str,
        action: str,
        level: str,
        status: str,
        title: str,
        message: str,
        stock_code: Optional[str] = None,
        stock_name: Optional[str] = None,
        task_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
    ) -> OperationLog:
        payload = json.dumps(details, ensure_ascii=False) if details is not None else None
        with self.db.session_scope() as session:
            row = OperationLog(
                category=category,
                action=action,
                level=level,
                status=status,
                title=title,
                message=message,
                stock_code=stock_code,
                stock_name=stock_name,
                task_id=task_id,
                details_json=payload,
                created_at=created_at or datetime.now(),
            )
            session.add(row)
            session.flush()
            session.refresh(row)
            return row

    def list_recent(
        self,
        *,
        limit: int = 100,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[OperationLog]:
        with self.db.get_session() as session:
            stmt = select(OperationLog).order_by(desc(OperationLog.created_at), desc(OperationLog.id)).limit(limit)
            if category:
                stmt = stmt.where(OperationLog.category == category)
            if status:
                stmt = stmt.where(OperationLog.status == status)
            return list(session.execute(stmt).scalars().all())
