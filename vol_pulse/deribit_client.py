from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Tuple

import os

try:
    import aiohttp
    from aiohttp import ClientError
except ModuleNotFoundError:  # allow mock-only runs without optional HTTP deps
    aiohttp = None  # type: ignore[assignment]

    class ClientError(Exception):
        """Fallback error type when aiohttp is unavailable."""

from .constants import BTC_INDEX_NAME, DERIBIT_BASE_URL, DVOL_SYMBOL


class DeribitRESTClient:
    def __init__(self) -> None:
        self.base_url = DERIBIT_BASE_URL
        self.proxy_url = self._build_proxy_url()

    @staticmethod
    def _ensure_http_client() -> None:
        if aiohttp is None:
            raise RuntimeError(
                "aiohttp is required for live Deribit API calls. Install dependencies with: pip install -r requirements.txt"
            )

    @staticmethod
    def _build_proxy_url() -> str | None:
        host = os.getenv("PROXY_HOST")
        port = os.getenv("PROXY_PORT")
        proxy_type = os.getenv("PROXY_TYPE", "http").lower()
        if not host or not port:
            return None
        scheme = "http" if proxy_type == "http" else "socks5"
        return f"{scheme}://{host}:{port}"

    async def _get(self, session: aiohttp.ClientSession, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/{path}"
        async with session.get(url, params=params, timeout=20, proxy=self.proxy_url) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data.get("result", {})

    async def get_index_price(self) -> float:
        self._ensure_http_client()
        async with aiohttp.ClientSession(trust_env=True) as session:
            result = await self._get_with_retry(session, "public/get_index_price", {"index_name": BTC_INDEX_NAME})
            return float(result.get("index_price", 0.0))

    async def get_dvol(self) -> float:
        self._ensure_http_client()
        async with aiohttp.ClientSession(trust_env=True) as session:
            data = await self._get_dvol_data(session, hours=6, resolution_min=3600)
            if not data:
                return 0.0
            return float(data[-1][4])

    async def get_dvol_history(self, days: int) -> List[float]:
        self._ensure_http_client()
        async with aiohttp.ClientSession(trust_env=True) as session:
            end_ts = int(time.time() * 1000)
            start_ts = end_ts - int(days) * 86400 * 1000
            try:
                result = await self._get(
                    session,
                    "public/get_volatility_index_data",
                    self._build_dvol_params(start_ts=start_ts, end_ts=end_ts, resolution_min=86400),
                )
            except (asyncio.TimeoutError, ClientError):
                return []

            data = result.get("data", [])
            return [float(item[4]) for item in data if len(item) > 4]

    async def _get_dvol_data(
        self, session: aiohttp.ClientSession, hours: int, resolution_min: int
    ) -> List[Tuple[float, float, float, float, float]]:
        result = await self._get(
            session,
            "public/get_volatility_index_data",
            self._build_dvol_params(
                start_ts=int(time.time() * 1000) - int(hours) * 3600 * 1000,
                end_ts=int(time.time() * 1000),
                resolution_min=resolution_min,
            ),
        )
        data = result.get("data", [])
        return [tuple(item) for item in data]

    @staticmethod
    def _build_dvol_params(
        *, start_ts: int, end_ts: int, resolution_min: int
    ) -> Dict[str, Any]:
        return {
            "currency": "BTC",
            "start_timestamp": start_ts,
            "end_timestamp": end_ts,
            "resolution": resolution_min,
        }

    async def get_option_chain(
        self, dte_range_days: Tuple[int, int] | None = None, option_type: str | None = None
    ) -> List[dict]:
        self._ensure_http_client()
        async with aiohttp.ClientSession(trust_env=True) as session:
            instruments = await self._get_with_retry(
                session,
                "public/get_instruments",
                {"currency": "BTC", "kind": "option", "expired": "false"},
            )
            instrument_names = self._filter_instruments(instruments, dte_range_days, option_type)
            quotes = await self._fetch_tickers(session, instrument_names)
            return quotes

    async def _fetch_tickers(self, session: aiohttp.ClientSession, names: List[str]) -> List[dict]:
        sem = asyncio.Semaphore(5)
        results: List[dict] = []

        async def _fetch_one(name: str) -> None:
            async with sem:
                result = await self._get_with_retry(session, "public/ticker", {"instrument_name": name})
                if not result:
                    return
                results.append(
                    {
                        "instrument_name": result.get("instrument_name"),
                        "strike": result.get("strike"),
                        "option_type": result.get("option_type"),
                        "expiration_timestamp": result.get("expiration_timestamp"),
                        "delta": (result.get("greeks") or {}).get("delta"),
                        "mark_iv": result.get("mark_iv"),
                        "bid": result.get("best_bid_price"),
                        "ask": result.get("best_ask_price"),
                    }
                )

        await asyncio.gather(*[_fetch_one(name) for name in names])
        return results

    @staticmethod
    def _filter_instruments(
        instruments: List[dict], dte_range_days: Tuple[int, int] | None, option_type: str | None
    ) -> List[str]:
        now_ts = int(time.time() * 1000)
        names: List[str] = []
        for item in instruments:
            if option_type and item.get("option_type") != option_type:
                continue
            exp_ts = int(item.get("expiration_timestamp", 0))
            if dte_range_days:
                dte_days = (exp_ts - now_ts) / 86400000.0
                if not (dte_range_days[0] <= dte_days <= dte_range_days[1]):
                    continue
            names.append(item["instrument_name"])
        return names

    async def _get_with_retry(
        self, session: aiohttp.ClientSession, path: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        delay = 0.25
        for _ in range(3):
            try:
                return await self._get(session, path, params)
            except (ClientError, asyncio.TimeoutError) as exc:
                status = getattr(exc, "status", None)
                if status != 429:
                    if isinstance(exc, asyncio.TimeoutError):
                        await asyncio.sleep(delay)
                        delay *= 2
                        continue
                    raise
                await asyncio.sleep(delay)
                delay *= 2
        return {}
