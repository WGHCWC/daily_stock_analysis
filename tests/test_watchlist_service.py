# -*- coding: utf-8 -*-
"""Tests for watchlist management service."""

import os
import tempfile
import threading
import time
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from src.config import Config
from src.core.config_manager import ConfigManager
from src.services.watchlist_service import (
    WatchlistDuplicateError,
    WatchlistError,
    WatchlistService,
    WatchlistTaskNotFoundError,
)
from src.storage import DatabaseManager, OperationLog


class WatchlistServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_path = Path(self.temp_dir.name) / ".env"
        self.db_path = Path(self.temp_dir.name) / "watchlist.db"
        self.env_path.write_text("STOCK_LIST=600519,000001\n", encoding="utf-8")
        os.environ["ENV_FILE"] = str(self.env_path)
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")
        self.manager = ConfigManager(env_path=self.env_path)
        self.service = WatchlistService(manager=self.manager, db_manager=self.db)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        self.temp_dir.cleanup()

    def test_list_watchlist_backfills_metadata_from_stock_list(self) -> None:
        def snapshot(
            code: str,
            preferred_name: str | None = None,
            include_intraday: bool = False,
            allow_history_fallback: bool = True,
            fetch_manager=None,
        ):
            mapping = {
                "600519": {"name": "贵州茅台", "current_price": 1800.0, "reference_price": 1800.0, "market_date": date(2026, 4, 3), "updated_at_dt": datetime(2026, 4, 3, 15, 10, 0)},
                "000001": {"name": "平安银行", "current_price": 12.0, "reference_price": 12.0, "market_date": date(2026, 4, 3), "updated_at_dt": datetime(2026, 4, 3, 15, 10, 0)},
            }
            return mapping[code]

        with patch.object(self.service, "_fetch_market_snapshot", side_effect=snapshot):
            items = self.service.list_watchlist()

        self.assertEqual([item["code"] for item in items], ["600519", "000001"])
        self.assertEqual(items[0]["name"], "贵州茅台")
        self.assertEqual(len(self.service._repo.list_all()), 2)

    def test_add_stock_updates_env_and_returns_item(self) -> None:
        with patch.object(
            self.service,
            "_fetch_market_snapshot",
            return_value={
                "name": "宁德时代",
                "current_price": 201.5,
                "reference_price": 201.5,
                "market_date": None,
                "updated_at_dt": None,
            },
        ) as fetch_snapshot:
            item = self.service.add_stock("300750")

        self.assertEqual(item["code"], "300750")
        self.assertEqual(item["name"], "宁德时代")
        self.assertEqual(fetch_snapshot.call_args.kwargs.get("allow_history_fallback"), False)
        env_content = self.env_path.read_text(encoding="utf-8")
        self.assertIn("STOCK_LIST=600519,000001,300750", env_content)

    def test_add_duplicate_stock_raises(self) -> None:
        with patch.object(
            self.service,
            "_fetch_market_snapshot",
            return_value={
                "name": "贵州茅台",
                "current_price": 1800.0,
                "reference_price": 1800.0,
                "market_date": None,
                "updated_at_dt": None,
            },
        ):
            with self.assertRaises(WatchlistDuplicateError):
                self.service.add_stock("600519")

    def test_add_stock_requires_basic_quote_data(self) -> None:
        with patch.object(
            self.service,
            "_fetch_market_snapshot",
            return_value={
                "name": "宁德时代",
                "current_price": None,
                "reference_price": None,
                "market_date": None,
                "updated_at_dt": None,
            },
        ):
            with self.assertRaises(WatchlistError):
                self.service.add_stock("300750")

    def test_list_watchlist_removes_rows_missing_from_stock_list(self) -> None:
        def snapshot(
            code: str,
            preferred_name: str | None = None,
            include_intraday: bool = False,
            allow_history_fallback: bool = True,
            fetch_manager=None,
        ):
            mapping = {
                "600519": {"name": "贵州茅台", "current_price": 1800.0, "reference_price": 1800.0, "market_date": date(2026, 4, 3), "updated_at_dt": datetime(2026, 4, 3, 15, 10, 0)},
                "000001": {"name": "平安银行", "current_price": 12.0, "reference_price": 12.0, "market_date": date(2026, 4, 3), "updated_at_dt": datetime(2026, 4, 3, 15, 10, 0)},
            }
            return mapping[code]

        with patch.object(self.service, "_fetch_market_snapshot", side_effect=snapshot):
            self.service.list_watchlist()

        self.manager.apply_updates(
            updates=[("STOCK_LIST", "600519")],
            sensitive_keys=set(),
            mask_token="******",
        )

        with patch.object(
            self.service,
            "_fetch_market_snapshot",
            return_value={
                "name": "贵州茅台",
                "current_price": 1810.0,
                "reference_price": 1810.0,
                "market_date": None,
                "updated_at_dt": None,
            },
        ):
            items = self.service.list_watchlist()

        self.assertEqual([item["code"] for item in items], ["600519"])
        self.assertEqual([row.code for row in self.service._repo.list_all()], ["600519"])

    def test_list_watchlist_uses_cached_gain_without_refresh(self) -> None:
        self.manager.apply_updates(
            updates=[("STOCK_LIST", "600519")],
            sensitive_keys=set(),
            mask_token="******",
        )
        self.service._repo.upsert(
            code="600519",
            name="贵州茅台",
            added_price=1500.0,
            cached_price=1650.0,
            cached_gain_percent=10.0,
            cache_updated_at=datetime(2026, 4, 3, 15, 30, 0),
            added_at=datetime(2026, 4, 1, 9, 0, 0),
        )

        with patch.object(self.service, "_should_refresh_cache", return_value=False):
            with patch.object(self.service, "_fetch_market_snapshot", side_effect=AssertionError("should not fetch")):
                items = self.service.list_watchlist()

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["current_price"], 1650.0)
        self.assertEqual(items[0]["gain_percent"], 10.0)

    def test_manual_refresh_updates_cached_gain(self) -> None:
        self.manager.apply_updates(
            updates=[("STOCK_LIST", "600519")],
            sensitive_keys=set(),
            mask_token="******",
        )
        self.service._repo.upsert(
            code="600519",
            name="贵州茅台",
            added_price=1500.0,
            cached_price=1650.0,
            cached_gain_percent=10.0,
            cache_updated_at=datetime(2026, 4, 2, 15, 30, 0),
            added_at=datetime(2026, 4, 1, 9, 0, 0),
        )

        with patch.object(
            self.service,
            "_fetch_market_snapshot",
            return_value={
                "name": "贵州茅台",
                "current_price": 1800.0,
                "reference_price": 1800.0,
                "market_date": date(2026, 4, 3),
                "updated_at_dt": datetime(2026, 4, 3, 16, 0, 0),
            },
        ):
            items = self.service.list_watchlist(force_refresh=True)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["current_price"], 1800.0)
        self.assertEqual(round(float(items[0]["gain_percent"]), 2), 20.0)

    def test_list_watchlist_does_not_use_history_fallback_for_incomplete_cache(self) -> None:
        self.manager.apply_updates(
            updates=[("STOCK_LIST", "300750")],
            sensitive_keys=set(),
            mask_token="******",
        )
        self.service._repo.upsert(
            code="300750",
            name="宁德时代",
            added_at=datetime(2026, 4, 1, 9, 0, 0),
        )

        captured_kwargs: list[dict] = []

        def snapshot(*args, **kwargs):
            captured_kwargs.append(kwargs)
            return {
                "name": "宁德时代",
                "current_price": None,
                "reference_price": None,
                "market_date": None,
                "updated_at_dt": datetime(2026, 4, 3, 10, 0, 0),
            }

        with patch.object(self.service, "_fetch_market_snapshot", side_effect=snapshot):
            items = self.service.list_watchlist()

        self.assertEqual(len(items), 1)
        self.assertTrue(captured_kwargs)
        self.assertTrue(all(call.get("allow_history_fallback") is False for call in captured_kwargs))

    def test_list_watchlist_uses_history_fallback_for_stale_complete_cache(self) -> None:
        self.manager.apply_updates(
            updates=[("STOCK_LIST", "600519")],
            sensitive_keys=set(),
            mask_token="******",
        )
        self.service._repo.upsert(
            code="600519",
            name="贵州茅台",
            added_price=1500.0,
            cached_price=1650.0,
            cached_gain_percent=10.0,
            cache_market_date=date(2026, 4, 2),
            cache_updated_at=datetime(2026, 4, 2, 15, 30, 0),
            added_at=datetime(2026, 4, 1, 9, 0, 0),
        )

        with patch.object(self.service, "_should_refresh_cache", return_value=True):
            with patch.object(
                self.service,
                "_fetch_market_snapshot",
                return_value={
                    "name": "贵州茅台",
                    "current_price": 1800.0,
                    "reference_price": 1800.0,
                    "market_date": date(2026, 4, 3),
                    "updated_at_dt": datetime(2026, 4, 3, 15, 10, 0),
                },
            ) as fetch_snapshot:
                items = self.service.list_watchlist()

        self.assertEqual(len(items), 1)
        self.assertTrue(fetch_snapshot.called)
        self.assertTrue(fetch_snapshot.call_args.kwargs.get("allow_history_fallback"))

    def test_repositories_recover_after_database_manager_reset(self) -> None:
        stale_repo = self.service._repo
        stale_log_service = self.service._operation_log_service

        DatabaseManager.reset_instance()
        fresh_db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")
        self.db = fresh_db

        row = stale_repo.upsert(code="300750", name="宁德时代", added_at=datetime(2026, 4, 3, 9, 0, 0))
        log = stale_log_service.record(
            category="watchlist",
            action="test_reset",
            title="repo recovered",
            message="repo recovered",
        )

        self.assertEqual(row.code, "300750")
        self.assertEqual(log["action"], "test_reset")
        with fresh_db.get_session() as session:
            logs = session.query(OperationLog).filter(OperationLog.action == "test_reset").all()
        self.assertEqual(len(logs), 1)

    def test_get_instance_reinitializes_stale_singleton(self) -> None:
        self.db._initialized = False

        recovered = DatabaseManager.get_instance()

        self.assertTrue(getattr(recovered, "_initialized", False))
        with recovered.get_session() as session:
            self.assertIsNotNone(session)

    def test_start_batch_add_runs_and_persists_results(self) -> None:
        def snapshot(
            code: str,
            preferred_name: str | None = None,
            include_intraday: bool = False,
            allow_history_fallback: bool = True,
            fetch_manager=None,
        ):
            mapping = {
                "600519": {
                    "name": "贵州茅台",
                    "current_price": 1800.0,
                    "reference_price": 1800.0,
                    "market_date": date(2026, 4, 3),
                    "updated_at_dt": datetime(2026, 4, 3, 15, 10, 0),
                },
                "000001": {
                    "name": "平安银行",
                    "current_price": 12.0,
                    "reference_price": 12.0,
                    "market_date": date(2026, 4, 3),
                    "updated_at_dt": datetime(2026, 4, 3, 15, 10, 0),
                },
                "300750": {
                    "name": "宁德时代",
                    "current_price": 201.5,
                    "reference_price": 201.5,
                    "market_date": date(2026, 4, 3),
                    "updated_at_dt": datetime(2026, 4, 3, 15, 10, 0),
                },
                "000858": {
                    "name": "五粮液",
                    "current_price": 132.8,
                    "reference_price": 132.8,
                    "market_date": date(2026, 4, 3),
                    "updated_at_dt": datetime(2026, 4, 3, 15, 10, 0),
                },
            }
            return mapping[code]

        with patch.object(self.service, "_fetch_market_snapshot", side_effect=snapshot):
            task = self.service.start_batch_add(["300750", "000858"], run_async=False)

        self.assertEqual(task["status"], "completed")
        self.assertEqual(task["total"], 2)
        self.assertEqual(task["completed"], 2)
        self.assertEqual([item["status"] for item in task["results"]], ["success", "success"])

        fetched_task = self.service.get_batch_add_task(task["task_id"])
        self.assertEqual(fetched_task["status"], "completed")
        env_content = self.env_path.read_text(encoding="utf-8")
        self.assertIn("STOCK_LIST=600519,000001,300750,000858", env_content)
        with self.db.get_session() as session:
            logs = session.query(OperationLog).order_by(OperationLog.id.asc()).all()
        self.assertEqual(len(logs), 3)
        self.assertEqual(logs[0].action, "batch_add_item")
        self.assertEqual(logs[0].status, "success")
        self.assertEqual(logs[-1].action, "batch_add_summary")

    def test_batch_add_records_item_errors(self) -> None:
        with patch.object(
            self.service,
            "_fetch_market_snapshot",
            return_value={
                "name": "宁德时代",
                "current_price": 201.5,
                "reference_price": 201.5,
                "market_date": date(2026, 4, 3),
                "updated_at_dt": datetime(2026, 4, 3, 15, 10, 0),
            },
        ):
            task = self.service.start_batch_add(["600519", "300750"], run_async=False)

        self.assertEqual(task["status"], "completed")
        self.assertEqual(task["completed"], 2)
        self.assertEqual(task["results"][0]["status"], "error")
        self.assertIn("已在自选股中", task["results"][0]["message"])
        self.assertEqual(task["results"][1]["status"], "success")
        with self.db.get_session() as session:
            logs = session.query(OperationLog).order_by(OperationLog.id.asc()).all()
        self.assertEqual(len(logs), 3)
        self.assertEqual(logs[0].status, "error")
        self.assertEqual(logs[1].status, "success")
        self.assertEqual(logs[2].status, "partial")

    def test_batch_add_skips_invalid_and_duplicate_inputs(self) -> None:
        with patch.object(
            self.service,
            "_fetch_market_snapshot",
            return_value={
                "name": "宁德时代",
                "current_price": 201.5,
                "reference_price": 201.5,
                "market_date": date(2026, 4, 3),
                "updated_at_dt": datetime(2026, 4, 3, 15, 10, 0),
            },
        ):
            task = self.service.start_batch_add(["bad-code", "300750", "300750", ""], run_async=False)

        self.assertEqual(task["status"], "completed")
        self.assertEqual(task["total"], 4)
        self.assertEqual(task["completed"], 4)
        self.assertEqual([item["status"] for item in task["results"]], ["error", "error", "error", "success"])
        self.assertIn("格式不正确", task["results"][0]["message"])
        self.assertIn("重复", task["results"][1]["message"])
        self.assertEqual(task["results"][3]["code"], "300750")

    def test_get_missing_batch_task_raises(self) -> None:
        with self.assertRaises(WatchlistTaskNotFoundError):
            self.service.get_batch_add_task("missing-task-id")

    def test_cancel_batch_add_task_stops_remaining_items(self) -> None:
        started = threading.Event()
        release = threading.Event()
        processed_codes: list[str] = []

        def fake_add_stock(
            stock_code: str,
            name: str | None = None,
            *,
            fetch_manager=None,
        ) -> dict:
            processed_codes.append(stock_code)
            started.set()
            if stock_code == "300750":
                release.wait(timeout=1.0)
            return {
                "code": stock_code,
                "name": stock_code,
                "added_at": None,
                "added_price": 10.0,
                "current_price": 10.0,
                "gain_percent": 0.0,
                "updated_at": None,
            }

        with patch.object(self.service, "add_stock", side_effect=fake_add_stock):
            task = self.service.start_batch_add(["300750", "000858", "000001"], run_async=True)
            self.assertTrue(started.wait(timeout=1.0))

            cancelling_task = self.service.cancel_batch_add_task(task["task_id"])
            self.assertEqual(cancelling_task["status"], "cancelled")

            release.set()
            deadline = time.time() + 2.0
            cancelled_task = None
            while time.time() < deadline:
                current = self.service.get_batch_add_task(task["task_id"])
                if current["status"] == "cancelled" and current["completed"] == 1:
                    cancelled_task = current
                    break
                time.sleep(0.05)

        self.assertIsNotNone(cancelled_task)
        assert cancelled_task is not None
        self.assertEqual(cancelled_task["status"], "cancelled")
        self.assertEqual(cancelled_task["completed"], 1)
        self.assertEqual(len(cancelled_task["results"]), 1)
        self.assertEqual(processed_codes, ["300750"])
        with self.db.get_session() as session:
            logs = session.query(OperationLog).order_by(OperationLog.id.asc()).all()
        self.assertEqual(logs[-1].status, "cancelled")


if __name__ == "__main__":
    unittest.main()
