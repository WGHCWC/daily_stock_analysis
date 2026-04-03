# -*- coding: utf-8 -*-
"""Tests for Tushare proxy endpoint configuration and official fallback."""

import json
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import requests

import data_provider.tushare_fetcher as tushare_fetcher_module


class _DummyApi:
    _DataApi__timeout = 9


class _DummyResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self.text = json.dumps(payload)


class _FakeTushareModule:
    def __init__(self, api):
        self._api = api
        self.tokens = []

    def set_token(self, token):
        self.tokens.append(token)

    def pro_api(self):
        return self._api


class TushareFetcherProxyFallbackTestCase(unittest.TestCase):
    def test_proxy_failure_falls_back_to_official_token(self) -> None:
        api = _DummyApi()
        fake_tushare = _FakeTushareModule(api)
        config = SimpleNamespace(
            tushare_token="official-token",
            tushare_proxy_url="https://proxy.example.com/tushare",
            tushare_proxy_token="proxy-token",
        )
        calls = []

        def fake_post(url, json, timeout):
            calls.append({"url": url, "json": json, "timeout": timeout})
            if len(calls) == 1:
                raise requests.RequestException("proxy unavailable")
            return _DummyResponse(
                200,
                {
                    "code": 0,
                    "data": {
                        "fields": ["ts_code", "trade_date"],
                        "items": [["600519.SH", "20240401"]],
                    },
                },
            )

        with patch.dict(sys.modules, {"tushare": fake_tushare}):
            with patch.object(tushare_fetcher_module, "get_config", return_value=config):
                with patch.object(tushare_fetcher_module.requests, "post", side_effect=fake_post):
                    fetcher = tushare_fetcher_module.TushareFetcher()
                    result = fetcher._api.query("daily", ts_code="600519.SH")

        self.assertEqual(fake_tushare.tokens, ["proxy-token"])
        self.assertEqual(fetcher.priority, -1)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["url"], "https://proxy.example.com/tushare")
        self.assertEqual(calls[0]["json"]["token"], "proxy-token")
        self.assertEqual(calls[1]["url"], fetcher.OFFICIAL_TUSHARE_API_URL)
        self.assertEqual(calls[1]["json"]["token"], "official-token")
        self.assertEqual(result.iloc[0]["ts_code"], "600519.SH")

    def test_official_token_remains_primary_when_no_proxy_is_configured(self) -> None:
        api = _DummyApi()
        fake_tushare = _FakeTushareModule(api)
        config = SimpleNamespace(
            tushare_token="legacy-token",
            tushare_proxy_url="",
            tushare_proxy_token="",
        )
        calls = []

        def fake_post(url, json, timeout):
            calls.append({"url": url, "json": json, "timeout": timeout})
            return _DummyResponse(
                200,
                {
                    "code": 0,
                    "data": {
                        "fields": ["ts_code", "trade_date"],
                        "items": [["000001.SZ", "20240402"]],
                    },
                },
            )

        with patch.dict(sys.modules, {"tushare": fake_tushare}):
            with patch.object(tushare_fetcher_module, "get_config", return_value=config):
                with patch.object(tushare_fetcher_module.requests, "post", side_effect=fake_post):
                    fetcher = tushare_fetcher_module.TushareFetcher()
                    result = fetcher._api.query("daily", ts_code="000001.SZ")

        self.assertEqual(fake_tushare.tokens, ["legacy-token"])
        self.assertEqual(fetcher.priority, -1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["url"], fetcher.OFFICIAL_TUSHARE_API_URL)
        self.assertEqual(calls[0]["json"]["token"], "legacy-token")
        self.assertEqual(result.iloc[0]["trade_date"], "20240402")


if __name__ == "__main__":
    unittest.main()
