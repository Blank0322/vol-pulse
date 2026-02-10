from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable, List, Tuple


@dataclass
class OptionCandidate:
    instrument_name: str
    strike: float
    expiration_ts: float
    delta: float
    mark_iv: float
    bid: float
    ask: float
    dte_days: float
    premium_btc: float
    annualized_yield: float
    safety_margin: float
    vrp: float


@dataclass
class SkewReport:
    skew: float | None
    signal: str
    pricing_error: bool
    skew_z: float | None


@dataclass
class TermStructureReport:
    iv_spread: float | None
    signal: str
    near_iv: float | None
    far_iv: float | None


class OpportunityScanner:
    def __init__(self, target_delta: tuple[float, float], dte_range_days: tuple[int, int]) -> None:
        self.delta_min, self.delta_max = target_delta
        self.dte_min, self.dte_max = dte_range_days

    def scan(
        self,
        options: Iterable[dict],
        spot_price: float,
        realized_vol_24h: float,
        now_ts: float | None = None,
    ) -> List[OptionCandidate]:
        now_ts = now_ts or time.time()
        candidates: List[OptionCandidate] = []
        for opt in options:
            if opt.get("option_type") != "put":
                continue

            delta = opt.get("delta")
            mark_iv = opt.get("mark_iv")
            if delta is None or mark_iv is None:
                continue

            abs_delta = abs(float(delta))
            if not (self.delta_min <= abs_delta <= self.delta_max):
                continue

            exp_ts = float(opt.get("expiration_timestamp", 0)) / 1000.0
            dte_days = (exp_ts - now_ts) / 86400.0
            if not (self.dte_min <= dte_days <= self.dte_max):
                continue

            bid = float(opt.get("bid", 0.0))
            ask = float(opt.get("ask", 0.0))
            premium_btc = self._mid_price(bid, ask)
            if premium_btc <= 0:
                continue

            strike = float(opt.get("strike", 0.0))
            safety_margin = (spot_price - strike) / spot_price
            annualized_yield = premium_btc * 365.0 / max(dte_days, 1e-6)
            vrp = float(mark_iv) - realized_vol_24h

            candidates.append(
                OptionCandidate(
                    instrument_name=opt.get("instrument_name", ""),
                    strike=strike,
                    expiration_ts=exp_ts,
                    delta=float(delta),
                    mark_iv=float(mark_iv),
                    bid=bid,
                    ask=ask,
                    dte_days=dte_days,
                    premium_btc=premium_btc,
                    annualized_yield=annualized_yield,
                    safety_margin=safety_margin,
                    vrp=vrp,
                )
            )
        return candidates

    def analyze_skew(
        self,
        options: Iterable[dict],
        target_delta: float = 0.20,
        skew_history: List[float] | None = None,
    ) -> SkewReport:
        skew_history = skew_history or []
        put_iv, call_iv = self._find_same_expiry_iv(options, target_delta)
        if put_iv is None or call_iv is None:
            return SkewReport(skew=None, signal="insufficient_data", pricing_error=False, skew_z=None)

        skew = put_iv - call_iv
        signal = "neutral"
        if skew > 0.15:
            signal = "bearish_put_premium"
        elif skew < 0.0:
            signal = "fomo_calls_rich"

        skew_z = None
        pricing_error = False
        if len(skew_history) >= 5:
            mean = sum(skew_history) / len(skew_history)
            var = sum((x - mean) ** 2 for x in skew_history) / max(len(skew_history) - 1, 1)
            std = var**0.5
            if std > 0:
                skew_z = (skew - mean) / std
                pricing_error = skew_z >= 2.0

        return SkewReport(skew=skew, signal=signal, pricing_error=pricing_error, skew_z=skew_z)

    def analyze_term_structure(
        self, options: Iterable[dict], near_days: int = 7, far_days: int = 30
    ) -> TermStructureReport:
        near_iv = self._median_iv_by_dte(options, near_days, window_days=2)
        far_iv = self._median_iv_by_dte(options, far_days, window_days=3)
        if near_iv is None or far_iv is None:
            return TermStructureReport(iv_spread=None, signal="insufficient_data", near_iv=near_iv, far_iv=far_iv)

        iv_spread = near_iv - far_iv
        if iv_spread > 0:
            signal = "near_term_pulse"
        else:
            signal = "normal_carry"
        return TermStructureReport(iv_spread=iv_spread, signal=signal, near_iv=near_iv, far_iv=far_iv)

    @staticmethod
    def _mid_price(bid: float, ask: float) -> float:
        if bid > 0 and ask > 0:
            return (bid + ask) / 2.0
        return max(bid, ask)

    @staticmethod
    def _find_same_expiry_iv(
        options: Iterable[dict], target_delta: float
    ) -> Tuple[float | None, float | None]:
        # Pick nearest-delta put/call pair from the same expiry.
        best = {}
        for opt in options:
            delta = opt.get("delta")
            mark_iv = opt.get("mark_iv")
            exp_ts = opt.get("expiration_timestamp")
            if delta is None or mark_iv is None or exp_ts is None:
                continue
            delta = float(delta)
            mark_iv = float(mark_iv)
            if opt.get("option_type") == "put":
                target = -abs(target_delta)
            elif opt.get("option_type") == "call":
                target = abs(target_delta)
            else:
                continue

            key = (exp_ts, opt.get("option_type"))
            distance = abs(delta - target)
            if key not in best or distance < best[key][0]:
                best[key] = (distance, mark_iv)

        expiries = {exp for exp, _ in best.keys()}
        for exp in expiries:
            put_key = (exp, "put")
            call_key = (exp, "call")
            if put_key in best and call_key in best:
                return best[put_key][1], best[call_key][1]
        return None, None

    @staticmethod
    def _median_iv_by_dte(
        options: Iterable[dict], target_days: int, window_days: int
    ) -> float | None:
        now_ts = time.time()
        values: List[float] = []
        for opt in options:
            exp_ts = opt.get("expiration_timestamp")
            mark_iv = opt.get("mark_iv")
            if exp_ts is None or mark_iv is None:
                continue
            dte_days = (float(exp_ts) / 1000.0 - now_ts) / 86400.0
            if abs(dte_days - target_days) <= window_days:
                values.append(float(mark_iv))
        if not values:
            return None
        values.sort()
        mid = len(values) // 2
        if len(values) % 2 == 1:
            return values[mid]
        return (values[mid - 1] + values[mid]) / 2.0
