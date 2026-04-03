# -*- coding: utf-8 -*-
"""Tests for operation log pagination service."""

import os
import tempfile
import unittest
from pathlib import Path

from src.config import Config
from src.services.operation_log_service import OperationLogService
from src.storage import DatabaseManager


class OperationLogServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_path = Path(self.temp_dir.name) / ".env"
        self.db_path = Path(self.temp_dir.name) / "operation_logs.db"
        self.env_path.write_text("STOCK_LIST=\n", encoding="utf-8")
        os.environ["ENV_FILE"] = str(self.env_path)
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")
        self.service = OperationLogService(db_manager=self.db)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        self.temp_dir.cleanup()

    def test_list_logs_paginates_with_max_page_size(self) -> None:
        for index in range(25):
            self.service.record(
                category="watchlist",
                action=f"action_{index}",
                title=f"title_{index}",
                message=f"message_{index}",
                status="success" if index % 2 == 0 else "error",
            )

        first_page = self.service.list_logs(page=1, page_size=20, category="watchlist")
        second_page = self.service.list_logs(page=2, page_size=20, category="watchlist")

        self.assertEqual(first_page["page"], 1)
        self.assertEqual(first_page["page_size"], 20)
        self.assertEqual(first_page["total"], 25)
        self.assertEqual(first_page["total_pages"], 2)
        self.assertEqual(len(first_page["items"]), 20)

        self.assertEqual(second_page["page"], 2)
        self.assertEqual(second_page["page_size"], 20)
        self.assertEqual(second_page["total"], 25)
        self.assertEqual(second_page["total_pages"], 2)
        self.assertEqual(len(second_page["items"]), 5)


if __name__ == "__main__":
    unittest.main()
