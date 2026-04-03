# -*- coding: utf-8 -*-
"""Watchlist management service."""

from __future__ import annotations

import logging
import re
import threading
from datetime import date, datetime, time
from math import isnan
from typing import Any, Dict, List, Optional
from uuid import uuid4
from zoneinfo import ZoneInfo

from data_provider.base import DataFetcherManager, canonical_stock_code
from src.config import Config, setup_env
from src.core.config_manager import ConfigManager
from src.core.trading_calendar import MARKET_TIMEZONE, get_market_for_stock, is_market_open
from src.services.operation_log_service import OperationLogService
from src.repositories.watchlist_repo import WatchlistRepository
from src.storage import DatabaseManager, WatchlistStock

logger = logging.getLogger(__name__)

MARKET_CLOSE_TIME = {
    "cn": time(hour=15, minute=0),
    "hk": time(hour=16, minute=10),
    "us": time(hour=16, minute=0),
}
WATCHLIST_BATCH_TASK_TTL_SECONDS = 24 * 60 * 60
WATCHLIST_CODE_PATTERNS = (
    re.compile(r"^\d{6}$"),
    re.compile(r"^(SH|SZ)\d{6}$", re.IGNORECASE),
    re.compile(r"^\d{5}$"),
    re.compile(r"^[A-Z]{1,6}(\.[A-Z]{1,2})?$", re.IGNORECASE),
)
WATCHLIST_ADD_REALTIME_SOURCES = ("tushare", "tencent", "akshare_sina")


class WatchlistError(Exception):
    """Base error for watchlist operations."""


class WatchlistDuplicateError(WatchlistError):
    """Raised when stock already exists in watchlist."""


class WatchlistNotFoundError(WatchlistError):
    """Raised when stock does not exist in watchlist."""


class WatchlistTaskNotFoundError(WatchlistError):
    """Raised when a watchlist batch task does not exist."""


class WatchlistService:
    """Synchronize watchlist metadata table with legacy STOCK_LIST config."""

    def __init__(
        self,
        *,
        manager: Optional[ConfigManager] = None,
        db_manager: Optional[DatabaseManager] = None,
        repo: Optional[WatchlistRepository] = None,
        operation_log_service: Optional[OperationLogService] = None,
    ):
        self._config_manager = manager or ConfigManager()
        self._db_manager = db_manager or DatabaseManager.get_instance()
        self._repo = repo or WatchlistRepository(db_manager=self._db_manager)
        self._operation_log_service = operation_log_service or OperationLogService(db_manager=self._db_manager)
        self._batch_tasks: Dict[str, Dict[str, Any]] = {}
        self._batch_tasks_lock = threading.Lock()

    def list_watchlist(self, *, force_refresh: bool = False) -> List[Dict[str, Any]]:
        rows_by_code = self._sync_watchlist_metadata(force_refresh=force_refresh)
        watch_codes = self._read_watch_codes()
        items: List[Dict[str, Any]] = []

        for code in watch_codes:
            row = rows_by_code.get(code)
            if row is None:
                continue
            row = self._ensure_cache(row, force_refresh=force_refresh)
            items.append(self._build_watchlist_item(row=row))

        return items

    def add_stock(
        self,
        stock_code: str,
        name: Optional[str] = None,
        *,
        fetch_manager: Optional[DataFetcherManager] = None,
    ) -> Dict[str, Any]:
        code = self._normalize_code(stock_code)
        watch_codes = self._read_watch_codes()
        if code in watch_codes or self._repo.get_by_code(code) is not None:
            raise WatchlistDuplicateError(f"{code} 已在自选股中")

        snapshot = self._fetch_market_snapshot(
            code,
            preferred_name=name,
            include_intraday=True,
            allow_history_fallback=False,
            fetch_manager=fetch_manager,
            preferred_realtime_sources=WATCHLIST_ADD_REALTIME_SOURCES,
            supplement_realtime_fields=False,
        )
        if snapshot.get("current_price") is None or snapshot.get("reference_price") is None:
            raise WatchlistError(f"{code} 基础行情获取失败，请稍后重试")
        gain_percent = self._compute_gain_percent(snapshot.get("reference_price"), snapshot.get("current_price"))
        row = self._repo.upsert(
            code=code,
            name=snapshot.get("name") or (name or "").strip() or None,
            added_at=datetime.now(),
            added_price=snapshot.get("reference_price"),
            cached_price=snapshot.get("current_price"),
            cached_gain_percent=gain_percent,
            cache_market_date=snapshot.get("market_date"),
            cache_updated_at=snapshot.get("updated_at_dt"),
        )
        self._write_watch_codes([*watch_codes, code])
        return self._build_watchlist_item(row=row)

    def delete_stock(self, stock_code: str) -> None:
        code = self._normalize_code(stock_code)
        self._sync_watchlist_metadata()
        watch_codes = self._read_watch_codes()
        if code not in watch_codes:
            raise WatchlistNotFoundError(f"{code} 不在自选股中")

        self._repo.delete_by_code(code)
        self._write_watch_codes([item for item in watch_codes if item != code])

    def start_batch_add(
        self,
        stock_codes: List[str],
        name: Optional[str] = None,
        *,
        run_async: bool = True,
    ) -> Dict[str, Any]:
        cleaned_codes: List[str] = []
        initial_results: List[Dict[str, str]] = []
        seen = set()
        for stock_code in stock_codes:
            raw_code = (stock_code or "").strip()
            normalized = self._normalize_code(raw_code)
            if not normalized or not self._is_valid_batch_stock_code(normalized):
                initial_results.append(
                    {
                        "code": raw_code or "(empty)",
                        "status": "error",
                        "message": "股票代码格式不正确，已跳过",
                    }
                )
                continue
            if normalized in seen:
                initial_results.append(
                    {
                        "code": normalized,
                        "status": "error",
                        "message": "同一批次中重复，已跳过",
                    }
                )
                continue
            seen.add(normalized)
            cleaned_codes.append(normalized)

        task_id = uuid4().hex
        now = datetime.now()
        task = {
            "task_id": task_id,
            "status": "running" if cleaned_codes else "completed",
            "total": len(stock_codes),
            "completed": len(initial_results),
            "results": initial_results,
            "requested_name": (name or "").strip() or None,
            "cancel_requested": False,
            "error_message": None,
            "created_at": now,
            "updated_at": now,
            "finished_at": None if cleaned_codes else now,
        }

        with self._batch_tasks_lock:
            self._cleanup_batch_tasks_locked(now=now)
            self._batch_tasks[task_id] = task

        if cleaned_codes and run_async:
            worker = threading.Thread(
                target=self._run_batch_add_task,
                args=(task_id, cleaned_codes, task["requested_name"]),
                daemon=True,
            )
            worker.start()
        elif cleaned_codes:
            self._run_batch_add_task(task_id, cleaned_codes, task["requested_name"])
        else:
            with self._batch_tasks_lock:
                stored_task = self._batch_tasks.get(task_id)
                if stored_task is not None:
                    stored_task["updated_at"] = now

        return self._serialize_batch_task(task)

    def get_batch_add_task(self, task_id: str) -> Dict[str, Any]:
        with self._batch_tasks_lock:
            self._cleanup_batch_tasks_locked()
            task = self._batch_tasks.get(task_id)
            if task is None:
                raise WatchlistTaskNotFoundError(f"批量添加任务不存在: {task_id}")
            return self._serialize_batch_task(task)

    def cancel_batch_add_task(self, task_id: str) -> Dict[str, Any]:
        with self._batch_tasks_lock:
            self._cleanup_batch_tasks_locked()
            task = self._batch_tasks.get(task_id)
            if task is None:
                raise WatchlistTaskNotFoundError(f"批量添加任务不存在: {task_id}")
            if task["status"] in {"completed", "failed", "cancelled"}:
                return self._serialize_batch_task(task)
            task["cancel_requested"] = True
            self._mark_batch_task_cancelled_locked(task)
            return self._serialize_batch_task(task)

    def _sync_watchlist_metadata(self, *, force_refresh: bool = False) -> Dict[str, WatchlistStock]:
        watch_codes = self._read_watch_codes()
        watched_set = set(watch_codes)
        rows = self._repo.list_all()
        rows_by_code = {row.code: row for row in rows}

        for code in list(rows_by_code.keys()):
            if code not in watched_set:
                self._repo.delete_by_code(code)
                rows_by_code.pop(code, None)

        for code in watch_codes:
            row = rows_by_code.get(code)
            if row is None:
                snapshot = self._fetch_market_snapshot(code, include_intraday=force_refresh)
                gain_percent = self._compute_gain_percent(snapshot.get("reference_price"), snapshot.get("current_price"))
                row = self._repo.upsert(
                    code=code,
                    name=snapshot.get("name"),
                    added_at=datetime.now(),
                    added_price=snapshot.get("reference_price"),
                    cached_price=snapshot.get("current_price"),
                    cached_gain_percent=gain_percent,
                    cache_market_date=snapshot.get("market_date"),
                    cache_updated_at=snapshot.get("updated_at_dt"),
                )
                rows_by_code[code] = row
                continue

            updates: Dict[str, Any] = {}
            if not row.name or row.added_price is None or row.cached_price is None:
                snapshot = self._fetch_market_snapshot(
                    code,
                    preferred_name=row.name,
                    include_intraday=force_refresh,
                    allow_history_fallback=force_refresh,
                )
                if (not row.name) and snapshot.get("name"):
                    updates["name"] = snapshot["name"]
                if row.added_price is None and snapshot.get("reference_price") is not None:
                    updates["added_price"] = snapshot["reference_price"]
                if row.cached_price is None and snapshot.get("current_price") is not None:
                    updates["cached_price"] = snapshot["current_price"]
                    updates["cached_gain_percent"] = self._compute_gain_percent(
                        updates.get("added_price", row.added_price),
                        snapshot.get("current_price"),
                    )
                    updates["cache_market_date"] = snapshot.get("market_date")
                    updates["cache_updated_at"] = snapshot.get("updated_at_dt")
                if updates:
                    row = self._repo.upsert(code=code, **updates)
                    rows_by_code[code] = row

        return rows_by_code

    def _ensure_cache(self, row: WatchlistStock, *, force_refresh: bool) -> WatchlistStock:
        if not force_refresh and not self._should_refresh_cache(row):
            return row

        snapshot = self._fetch_market_snapshot(
            row.code,
            preferred_name=row.name,
            include_intraday=force_refresh,
            allow_history_fallback=force_refresh or self._has_complete_cache(row),
        )
        if (
            not force_refresh
            and row.cached_price is not None
            and row.cache_market_date is not None
            and snapshot.get("market_date") is not None
            and snapshot["market_date"] <= row.cache_market_date
        ):
            return row

        updates: Dict[str, Any] = {}
        if snapshot.get("name") and snapshot.get("name") != row.name:
            updates["name"] = snapshot["name"]
        if row.added_price is None and snapshot.get("reference_price") is not None:
            updates["added_price"] = snapshot["reference_price"]
        if snapshot.get("current_price") is not None:
            updates["cached_price"] = snapshot["current_price"]
            updates["cached_gain_percent"] = self._compute_gain_percent(
                updates.get("added_price", row.added_price),
                snapshot.get("current_price"),
            )
            updates["cache_market_date"] = snapshot.get("market_date")
            updates["cache_updated_at"] = snapshot.get("updated_at_dt")

        if not updates:
            return row
        return self._repo.upsert(code=row.code, **updates)

    def _build_watchlist_item(self, *, row: WatchlistStock) -> Dict[str, Any]:
        return {
            "code": row.code,
            "name": row.name or row.code,
            "added_at": row.added_at.isoformat() if row.added_at else None,
            "added_price": row.added_price,
            "current_price": row.cached_price,
            "gain_percent": row.cached_gain_percent,
            "updated_at": row.cache_updated_at.isoformat() if row.cache_updated_at else None,
        }

    def _fetch_market_snapshot(
        self,
        code: str,
        preferred_name: Optional[str] = None,
        *,
        include_intraday: bool = False,
        allow_history_fallback: bool = True,
        fetch_manager: Optional[DataFetcherManager] = None,
        preferred_realtime_sources: Optional[List[str] | tuple[str, ...]] = None,
        supplement_realtime_fields: bool = True,
    ) -> Dict[str, Any]:
        name = (preferred_name or "").strip() or None
        current_price: Optional[float] = None
        reference_price: Optional[float] = None
        market_date: Optional[date] = None
        updated_at_dt = datetime.now()

        try:
            manager = fetch_manager
            if include_intraday:
                manager = manager or DataFetcherManager()
                quote = manager.get_realtime_quote(
                    code,
                    source_priority=list(preferred_realtime_sources) if preferred_realtime_sources else None,
                    supplement_missing_fields=supplement_realtime_fields,
                )
                if quote is not None:
                    quote_name = getattr(quote, "name", None)
                    quote_price = self._to_float(getattr(quote, "price", None))
                    if quote_name:
                        name = quote_name
                    if quote_price is not None:
                        current_price = quote_price
                        reference_price = quote_price
                    updated_at_dt = datetime.now()
                    market_date = updated_at_dt.date()

            if not name:
                manager = manager or DataFetcherManager()
                resolved_name = manager.get_stock_name(code, allow_realtime=False)
                if resolved_name:
                    name = resolved_name

            if allow_history_fallback and (current_price is None or reference_price is None or market_date is None):
                manager = manager or DataFetcherManager()
                history_df, _ = manager.get_daily_data(code, days=5)
                if history_df is not None and not history_df.empty:
                    latest = history_df.sort_values("date").iloc[-1]
                    latest_close = self._to_float(latest.get("close"))
                    latest_date = latest.get("date")
                    if hasattr(latest_date, "date"):
                        market_date = latest_date.date()
                    elif isinstance(latest_date, date):
                        market_date = latest_date
                    elif latest_date is not None:
                        try:
                            market_date = datetime.fromisoformat(str(latest_date)).date()
                        except ValueError:
                            market_date = None
                    if latest_close is not None:
                        reference_price = reference_price or latest_close
                        if not include_intraday or current_price is None:
                            current_price = latest_close
        except Exception as exc:
            logger.warning("获取自选股快照失败 %s: %s", code, exc)

        return {
            "name": name,
            "current_price": current_price,
            "reference_price": reference_price,
            "market_date": market_date,
            "updated_at_dt": updated_at_dt,
        }

    def _should_refresh_cache(self, row: WatchlistStock) -> bool:
        if row.cached_price is None or row.cache_market_date is None or row.cache_updated_at is None:
            return True

        market = get_market_for_stock(row.code) or "cn"
        now_local = self._get_market_now(market)
        today_local = now_local.date()
        if is_market_open(market, today_local):
            close_time = MARKET_CLOSE_TIME.get(market, time(hour=16, minute=0))
            return now_local.time() >= close_time and row.cache_market_date < today_local

        return row.cache_updated_at.date() < datetime.now().date()

    @staticmethod
    def _has_complete_cache(row: WatchlistStock) -> bool:
        return (
            row.cached_price is not None
            and row.cache_market_date is not None
            and row.cache_updated_at is not None
        )

    @staticmethod
    def _compute_gain_percent(added_price: Optional[float], current_price: Optional[float]) -> Optional[float]:
        if added_price is None or current_price is None:
            return None
        try:
            return ((float(current_price) - float(added_price)) / float(added_price)) * 100
        except (TypeError, ZeroDivisionError, ValueError):
            return None

    @staticmethod
    def _get_market_now(market: str) -> datetime:
        tz_name = MARKET_TIMEZONE.get(market, "Asia/Shanghai")
        return datetime.now(ZoneInfo(tz_name))

    def _get_market_snapshot(self, code: str, preferred_name: Optional[str] = None) -> Dict[str, Any]:
        """Backward-compatible wrapper for tests/mocks added in previous iteration."""
        return self._fetch_market_snapshot(code, preferred_name=preferred_name, include_intraday=True)

    def _run_batch_add_task(self, task_id: str, stock_codes: List[str], name: Optional[str]) -> None:
        single_name = name if len(stock_codes) == 1 else None
        fetch_manager = DataFetcherManager()
        try:
            for stock_code in stock_codes:
                with self._batch_tasks_lock:
                    task = self._batch_tasks.get(task_id)
                    if task is None:
                        return
                    if task.get("cancel_requested"):
                        self._mark_batch_task_cancelled_locked(task)
                        break
                try:
                    item = self.add_stock(stock_code, name=single_name, fetch_manager=fetch_manager)
                    result = {
                        "code": stock_code,
                        "status": "success",
                        "message": "已加入自选股",
                        "item": item,
                    }
                    self._operation_log_service.record(
                        category="watchlist",
                        action="batch_add_item",
                        level="info",
                        status="success",
                        title="自选股新增成功",
                        message=f"{stock_code} 已加入自选股",
                        stock_code=stock_code,
                        stock_name=item.get("name"),
                        task_id=task_id,
                        details={
                            "task_id": task_id,
                            "result": result,
                            "source": "watchlist_batch_add",
                        },
                    )
                except Exception as exc:
                    result = {
                        "code": stock_code,
                        "status": "error",
                        "message": str(exc),
                    }
                    self._operation_log_service.record(
                        category="watchlist",
                        action="batch_add_item",
                        level="warning",
                        status="error",
                        title="自选股新增失败",
                        message=f"{stock_code} 添加失败: {str(exc)}",
                        stock_code=stock_code,
                        task_id=task_id,
                        details={
                            "task_id": task_id,
                            "result": result,
                            "source": "watchlist_batch_add",
                        },
                    )

                with self._batch_tasks_lock:
                    task = self._batch_tasks.get(task_id)
                    if task is None:
                        return
                    task["results"].append(result)
                    task["completed"] = min(task["completed"] + 1, task["total"])
                    task["updated_at"] = datetime.now()

            with self._batch_tasks_lock:
                task = self._batch_tasks.get(task_id)
                if task is None:
                    return
                if task.get("cancel_requested"):
                    self._mark_batch_task_cancelled_locked(task)
                elif task["status"] not in {"failed", "cancelled"}:
                    task["status"] = "completed"
                    task["finished_at"] = datetime.now()
                    task["updated_at"] = task["finished_at"]
                summary_results = list(task["results"])
                completed = task["completed"]
                total = task["total"]
                task_status = task["status"]
            success_count = sum(1 for item in summary_results if item["status"] == "success")
            error_count = sum(1 for item in summary_results if item["status"] == "error")
            self._operation_log_service.record(
                category="watchlist",
                action="batch_add_summary",
                level="warning" if task_status == "cancelled" or error_count > 0 else "info",
                status="cancelled" if task_status == "cancelled" else ("success" if error_count == 0 else "partial"),
                title="自选股批量新增已取消" if task_status == "cancelled" else "自选股批量新增完成",
                message=(
                    f"批量新增已取消，已处理 {completed} / {total} 条，成功 {success_count} 条，失败 {error_count} 条"
                    if task_status == "cancelled"
                    else f"批量新增完成，成功 {success_count} 条，失败 {error_count} 条"
                ),
                task_id=task_id,
                details={
                    "task_id": task_id,
                    "status": task_status,
                    "completed": completed,
                    "total": total,
                    "results": summary_results,
                },
            )
        except Exception as exc:
            logger.error("自选股批量添加任务失败 %s: %s", task_id, exc, exc_info=True)
            with self._batch_tasks_lock:
                task = self._batch_tasks.get(task_id)
                if task is None:
                    return
                task["status"] = "failed"
                task["error_message"] = str(exc)
                task["finished_at"] = datetime.now()
                task["updated_at"] = task["finished_at"]
            self._operation_log_service.record(
                category="watchlist",
                action="batch_add_summary",
                level="error",
                status="error",
                title="自选股批量新增任务失败",
                message=f"任务 {task_id} 执行失败: {str(exc)}",
                task_id=task_id,
                details={
                    "task_id": task_id,
                    "error_message": str(exc),
                    "source": "watchlist_batch_add",
                },
            )

    @staticmethod
    def _mark_batch_task_cancelled_locked(task: Dict[str, Any]) -> None:
        if task["status"] == "cancelled":
            return
        task["status"] = "cancelled"
        task["finished_at"] = datetime.now()
        task["updated_at"] = task["finished_at"]

    def _cleanup_batch_tasks_locked(self, *, now: Optional[datetime] = None) -> None:
        current = now or datetime.now()
        expired_task_ids = [
            task_id
            for task_id, task in self._batch_tasks.items()
            if task.get("finished_at") is not None
            and (current - task["finished_at"]).total_seconds() > WATCHLIST_BATCH_TASK_TTL_SECONDS
        ]
        for task_id in expired_task_ids:
            self._batch_tasks.pop(task_id, None)

    @staticmethod
    def _serialize_batch_task(task: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "task_id": task["task_id"],
            "status": task["status"],
            "total": task["total"],
            "completed": task["completed"],
            "results": list(task["results"]),
            "error_message": task.get("error_message"),
            "created_at": task["created_at"].isoformat() if task.get("created_at") else None,
            "updated_at": task["updated_at"].isoformat() if task.get("updated_at") else None,
            "finished_at": task["finished_at"].isoformat() if task.get("finished_at") else None,
        }

    @staticmethod
    def _is_valid_batch_stock_code(stock_code: str) -> bool:
        return any(pattern.match(stock_code) for pattern in WATCHLIST_CODE_PATTERNS)

    def _read_watch_codes(self) -> List[str]:
        config_map = self._config_manager.read_config_map()
        raw_value = config_map.get("STOCK_LIST", "")
        result: List[str] = []
        seen = set()
        for item in raw_value.split(","):
            code = self._normalize_code(item)
            if not code or code in seen:
                continue
            seen.add(code)
            result.append(code)
        return result

    def _write_watch_codes(self, codes: List[str]) -> None:
        cleaned: List[str] = []
        seen = set()
        for code in codes:
            normalized = self._normalize_code(code)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            cleaned.append(normalized)

        self._config_manager.apply_updates(
            updates=[("STOCK_LIST", ",".join(cleaned))],
            sensitive_keys=set(),
            mask_token="******",
        )
        Config.reset_instance()
        setup_env(override=True)

    @staticmethod
    def _normalize_code(stock_code: str) -> str:
        return canonical_stock_code(stock_code or "")

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            result = float(value)
        except (TypeError, ValueError):
            return None
        if isnan(result):
            return None
        return result
