from __future__ import annotations

import argparse
import asyncio
import os
import time
from collections import deque

from .alert_system import AlertMessage, AlertSystem
from .constants import (
    ACCOUNT_BALANCE,
    ENTRY_IVP_THRESHOLD,
    ENTRY_IVR_THRESHOLD,
    ENTRY_PRICE_DROP_1H,
    LOOKBACK_PERIOD,
    MAX_NOTIONAL_LIMIT,
    MIN_DVOL_PULSE,
    OPTION_DTE_RANGE_DAYS,
    SLOW_BLEED_DVOL_MAX_1H,
    SLOW_BLEED_PRICE_DROP_1H,
    TARGET_DELTA,
)
from .deribit_client import DeribitRESTClient
from .mock_data import MockDataGenerator
from .opportunity_scanner import OpportunityScanner
from .risk_engine import RiskEngine, RiskLimits
from .volatility_analyzer import VolatilityAnalyzer


def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = value


def _find_change_over_window(points: deque, now_ts: float, window_seconds: int) -> float | None:
    if not points:
        return None
    cutoff = now_ts - window_seconds
    oldest = None
    for ts, value in points:
        if ts >= cutoff:
            oldest = value
            break
    if oldest is None:
        return None
    latest = points[-1][1]
    if oldest == 0:
        return None
    return (latest - oldest) / oldest


async def run_monitor(use_mock: bool, poll_interval: float, verbose: bool, once: bool = False) -> None:
    alert = AlertSystem()
    analyzer = VolatilityAnalyzer(lookback_days=LOOKBACK_PERIOD)
    scanner = OpportunityScanner(target_delta=TARGET_DELTA, dte_range_days=OPTION_DTE_RANGE_DAYS)
    risk = RiskEngine(account_balance=ACCOUNT_BALANCE, limits=RiskLimits(max_single_btc=0.10, max_total_btc=0.20))
    skew_history: list[float] = []

    price_points = deque()
    dvol_points = deque()

    client = DeribitRESTClient()
    if use_mock:
        mock = MockDataGenerator()
        dvol_history = [
            mock.base_dvol * (0.85 + 0.15 * (1 + __import__("math").sin(i / 12.0)) / 2.0)
            for i in range(LOOKBACK_PERIOD)
        ]
        analyzer.set_dvol_history(dvol_history)
    else:
        dvol_history = await client.get_dvol_history(LOOKBACK_PERIOD)
        analyzer.set_dvol_history(dvol_history)

    while True:
        now_ts = time.time()
        if use_mock and not price_points and not dvol_points:
            price_points.append((now_ts - 3600, mock.base_spot))
            dvol_points.append((now_ts - 3600, mock.base_dvol))
        if use_mock:
            snapshot = mock.make_panic_snapshot()
            spot_price = snapshot.spot_price
            dvol = snapshot.dvol
            realized_vol_24h = snapshot.realized_vol_24h
            options = snapshot.options
        else:
            try:
                spot_price = await client.get_index_price()
                dvol = await client.get_dvol()
                realized_vol_24h = max(dvol / 100.0 - 0.1, 0.0)
                options = await client.get_option_chain(dte_range_days=(14, 30), option_type="put")
            except Exception as exc:  # keep loop alive on transient network failures
                if verbose:
                    print(f"Fetch error: {exc}")
                await asyncio.sleep(poll_interval)
                continue

        analyzer.add_dvol_point(now_ts, dvol)
        price_points.append((now_ts, spot_price))
        dvol_points.append((now_ts, dvol))

        while price_points and price_points[0][0] < now_ts - 7200:
            price_points.popleft()
        while dvol_points and dvol_points[0][0] < now_ts - 7200:
            dvol_points.popleft()

        price_change_1h = _find_change_over_window(price_points, now_ts, 3600)
        dvol_change_1h = _find_change_over_window(dvol_points, now_ts, 3600)
        metrics = analyzer.compute_metrics(dvol)

        if verbose:
            ivp = metrics.ivp if metrics.ivp is not None else 0.0
            ivr = metrics.ivr if metrics.ivr is not None else 0.0
            price_change = price_change_1h if price_change_1h is not None else 0.0
            dvol_change = dvol_change_1h if dvol_change_1h is not None else 0.0
            print(
                f"Spot {spot_price:.0f}, DVOL {dvol:.2f}, IVP {ivp:.1f}, IVR {ivr:.1f}, "
                f"Price1h {price_change:.2%}, DVOL1h {dvol_change:.2%}"
            )

        entry_signal = (
            price_change_1h is not None
            and dvol_change_1h is not None
            and price_change_1h <= ENTRY_PRICE_DROP_1H
            and dvol_change_1h >= MIN_DVOL_PULSE
            and ((metrics.ivp or 0) > ENTRY_IVP_THRESHOLD or (metrics.ivr or 0) > ENTRY_IVR_THRESHOLD)
        )

        slow_bleed = (
            price_change_1h is not None
            and dvol_change_1h is not None
            and price_change_1h <= SLOW_BLEED_PRICE_DROP_1H
            and dvol_change_1h <= SLOW_BLEED_DVOL_MAX_1H
        )

        if verbose:
            print(
                f"SignalCheck: entry={entry_signal}, slow_bleed={slow_bleed}, "
                f"rule_price<={ENTRY_PRICE_DROP_1H:.2%}, rule_dvol>={MIN_DVOL_PULSE:.2%}, "
                f"rule_iv=(IVP>{ENTRY_IVP_THRESHOLD:.0f} or IVR>{ENTRY_IVR_THRESHOLD:.0f})"
            )

        if slow_bleed:
            alert.send(
                AlertMessage(
                    title="Slow Bleed Trap",
                    body=(
                        f"Price down {price_change_1h:.2%} with DVOL {dvol_change_1h:.2%} (flat/down). "
                        "Block Sell Put scanning for this cycle."
                    ),
                )
            )

        if entry_signal and not slow_bleed:
            candidates = scanner.scan(options, spot_price, realized_vol_24h, now_ts)
            if not candidates:
                if verbose:
                    print("Entry triggered but no 14-30D put candidates in delta 0.15-0.20")
            else:
                candidates.sort(key=lambda c: (c.annualized_yield, c.safety_margin), reverse=True)
                top = candidates[0]
                max_contracts = risk.max_contracts_allowed()
                report = risk.estimate_margin_and_drawdown(
                    spot_price=spot_price,
                    strike=top.strike,
                    premium_btc=top.premium_btc,
                    iv=top.mark_iv,
                    contracts_btc=max_contracts,
                )
                skew_report = scanner.analyze_skew(options, target_delta=0.20, skew_history=skew_history)
                if skew_report.skew is not None:
                    skew_history.append(skew_report.skew)
                    if len(skew_history) > 120:
                        skew_history.pop(0)
                term_report = scanner.analyze_term_structure(options, near_days=7, far_days=30)
                term_hint = "7d" if term_report.signal == "near_term_pulse" else "14-30d"

                ivp_value = metrics.ivp if metrics.ivp is not None else 0.0
                ivr_value = metrics.ivr if metrics.ivr is not None else 0.0
                skew_value = skew_report.skew if skew_report.skew is not None else 0.0
                term_spread = term_report.iv_spread if term_report.iv_spread is not None else 0.0

                alert.send(
                    AlertMessage(
                        title="IV Pulse Entry",
                        body=(
                            f"Spot {spot_price:.0f}, DVOL {dvol:.1f}, IVP {ivp_value:.1f}, IVR {ivr_value:.1f}\n"
                            f"Suggested: Sell {top.instrument_name} (delta {top.delta:.2f}, DTE {top.dte_days:.1f})\n"
                            f"Yield {top.annualized_yield:.2%}, Safety {top.safety_margin:.2%}, VRP {top.vrp:.2f}\n"
                            f"Max contracts {report.max_contracts:.2f} BTC, Margin shock {report.est_margin_shock:.0f} USD\n"
                            f"Skew {skew_value:.2%} ({skew_report.signal}), PricingError {skew_report.pricing_error}\n"
                            f"TermSpread {term_spread:.2%} ({term_report.signal}), Prefer {term_hint}"
                        ),
                    )
                )

        if once:
            break

        await asyncio.sleep(poll_interval)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="Use mock market data")
    parser.add_argument("--interval", type=float, default=30.0, help="Polling interval in seconds")
    parser.add_argument("--verbose", action="store_true", help="Print status each poll")
    parser.add_argument("--once", action="store_true", help="Run one strategy cycle and exit")
    args = parser.parse_args()
    _load_dotenv()
    asyncio.run(run_monitor(use_mock=args.mock, poll_interval=args.interval, verbose=args.verbose, once=args.once))


if __name__ == "__main__":
    main()
