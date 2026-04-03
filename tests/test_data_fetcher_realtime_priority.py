# -*- coding: utf-8 -*-
"""Tests for realtime quote priority overrides."""

from __future__ import annotations

import unittest

from data_provider.base import DataFetcherManager
from data_provider.realtime_types import RealtimeSource, UnifiedRealtimeQuote


class _NullFetcher:
    priority = 99

    def __init__(self, name: str):
        self.name = name


class _QuoteFetcher:
    priority = 99

    def __init__(self, name: str, quote: UnifiedRealtimeQuote):
        self.name = name
        self._quote = quote
        self.calls: list[str] = []

    def get_realtime_quote(self, stock_code: str, *args, **kwargs):
        self.calls.append(stock_code)
        return self._quote


class DataFetcherRealtimePriorityTestCase(unittest.TestCase):
    def test_preferred_priority_uses_tushare_first_without_supplement(self) -> None:
        tushare_fetcher = _QuoteFetcher(
            "TushareFetcher",
            UnifiedRealtimeQuote(
                code="600519",
                name="贵州茅台",
                source=RealtimeSource.TUSHARE,
                price=1800.0,
            ),
        )
        tencent_fetcher = _QuoteFetcher(
            "AkshareFetcher",
            UnifiedRealtimeQuote(
                code="600519",
                name="贵州茅台",
                source=RealtimeSource.TENCENT,
                price=1801.0,
            ),
        )
        manager = DataFetcherManager(
            fetchers=[
                _NullFetcher("EfinanceFetcher"),
                tencent_fetcher,
                tushare_fetcher,
            ]
        )

        quote = manager.get_realtime_quote(
            "600519",
            source_priority=["tushare", "tencent"],
            supplement_missing_fields=False,
        )

        self.assertIsNotNone(quote)
        self.assertEqual(getattr(quote, "source", None), RealtimeSource.TUSHARE)
        self.assertEqual(tushare_fetcher.calls, ["600519"])
        self.assertEqual(tencent_fetcher.calls, [])


if __name__ == "__main__":
    unittest.main()
