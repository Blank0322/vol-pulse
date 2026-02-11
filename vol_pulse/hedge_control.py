from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HedgePlan:
    hedge_ratio: float
    reason: str


@dataclass(frozen=True)
class RiskInterrupt:
    triggered: bool
    reason: str | None = None


def dynamic_hedge_ratio(*, dvol: float, skew_z: float | None, drawdown_pct: float) -> HedgePlan:
    """Rule-based hedge ratio using historical-extreme style thresholds.

    Returns hedge ratio in [0, 1], where 1 means fully hedge directional exposure.
    """
    ratio = 0.2
    reasons = []

    if dvol >= 65:
        ratio = max(ratio, 0.8)
        reasons.append("DVOL extreme>=65")
    elif dvol >= 55:
        ratio = max(ratio, 0.5)
        reasons.append("DVOL elevated>=55")

    if skew_z is not None and abs(skew_z) >= 2.0:
        ratio = max(ratio, 0.7)
        reasons.append("skew 2σ deviation")

    if drawdown_pct <= -0.06:
        ratio = 1.0
        reasons.append("drawdown breach <= -6%")

    return HedgePlan(hedge_ratio=min(max(ratio, 0.0), 1.0), reason=", ".join(reasons) or "baseline")


def risk_interrupt(*, drawdown_pct: float, dvol: float, margin_utilization: float) -> RiskInterrupt:
    """Kill-switch style interrupt rule."""
    if drawdown_pct <= -0.10:
        return RiskInterrupt(True, "kill-switch: drawdown <= -10%")
    if dvol >= 75:
        return RiskInterrupt(True, "kill-switch: DVOL panic >= 75")
    if margin_utilization >= 0.85:
        return RiskInterrupt(True, "kill-switch: margin utilization >= 85%")
    return RiskInterrupt(False, None)
