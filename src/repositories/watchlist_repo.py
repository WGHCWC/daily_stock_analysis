# -*- coding: utf-8 -*-
"""
===================================
自选股元数据访问层
===================================

职责：
1. 封装 watchlist_stocks 表的 CRUD 操作
2. 为 Web 自选股管理页提供基础存储能力
"""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import delete, select

from src.storage import DatabaseManager, WatchlistStock


class WatchlistRepository:
    """自选股元数据仓储。"""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self._db_manager = db_manager

    @property
    def db(self) -> DatabaseManager:
        db_manager = self._db_manager
        if db_manager is None or not getattr(db_manager, "_initialized", False):
            db_manager = DatabaseManager.get_instance()
            self._db_manager = db_manager
        return db_manager

    def list_all(self) -> List[WatchlistStock]:
        with self.db.get_session() as session:
            rows = session.execute(
                select(WatchlistStock).order_by(WatchlistStock.added_at.asc(), WatchlistStock.id.asc())
            ).scalars().all()
            return list(rows)

    def get_by_code(self, code: str) -> Optional[WatchlistStock]:
        with self.db.get_session() as session:
            return session.execute(
                select(WatchlistStock).where(WatchlistStock.code == code)
            ).scalar_one_or_none()

    def upsert(
        self,
        *,
        code: str,
        name: Optional[str] = None,
        added_at: Optional[datetime] = None,
        added_price: Optional[float] = None,
        cached_price: Optional[float] = None,
        cached_gain_percent: Optional[float] = None,
        cache_market_date: Optional[date] = None,
        cache_updated_at: Optional[datetime] = None,
    ) -> WatchlistStock:
        with self.db.session_scope() as session:
            row = session.execute(
                select(WatchlistStock).where(WatchlistStock.code == code)
            ).scalar_one_or_none()
            if row is None:
                row = WatchlistStock(
                    code=code,
                    name=name,
                    added_at=added_at or datetime.now(),
                    added_price=added_price,
                    cached_price=cached_price,
                    cached_gain_percent=cached_gain_percent,
                    cache_market_date=cache_market_date,
                    cache_updated_at=cache_updated_at,
                )
                session.add(row)
                session.flush()
                session.refresh(row)
                return row

            if name:
                row.name = name
            if added_at is not None:
                row.added_at = added_at
            if added_price is not None:
                row.added_price = added_price
            if cached_price is not None:
                row.cached_price = cached_price
            if cached_gain_percent is not None:
                row.cached_gain_percent = cached_gain_percent
            if cache_market_date is not None:
                row.cache_market_date = cache_market_date
            if cache_updated_at is not None:
                row.cache_updated_at = cache_updated_at
            session.flush()
            session.refresh(row)
            return row

    def delete_by_code(self, code: str) -> bool:
        with self.db.session_scope() as session:
            result = session.execute(
                delete(WatchlistStock).where(WatchlistStock.code == code)
            )
            return bool(result.rowcount)
