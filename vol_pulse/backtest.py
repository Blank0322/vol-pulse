from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class BacktestConfig:
    price_drop_threshold_1h: float = -0.03
    dvol_pulse_threshold_1h: float = 0.10
    hold_hours: int = 24
    fee_bps_roundtrip: float = 10.0


@dataclass(frozen=True)
class BacktestResult:
    trades: int
    win_rate: float
    avg_return: float
    cumulative_return: float


def generate_signal(df: pd.DataFrame, cfg: BacktestConfig) -> pd.Series:
    """Signal: panic + vol expansion.

    Required columns:
    - spot
    - dvol
    Data frequency assumed hourly.
    """
    d = df.copy()
    d["spot_chg_1h"] = d["spot"].pct_change(1)
    d["dvol_chg_1h"] = d["dvol"].pct_change(1)
    sig = (d["spot_chg_1h"] <= cfg.price_drop_threshold_1h) & (
        d["dvol_chg_1h"] >= cfg.dvol_pulse_threshold_1h
    )
    return sig.fillna(False)


def run_backtest(df: pd.DataFrame, cfg: BacktestConfig | None = None) -> BacktestResult:
    cfg = cfg or BacktestConfig()
    d = df.copy().reset_index(drop=True)
    if not {"spot", "dvol"}.issubset(d.columns):
        raise ValueError("DataFrame must include columns: spot, dvol")

    signal = generate_signal(d, cfg)
    rets = d["spot"].pct_change(cfg.hold_hours).shift(-cfg.hold_hours)

    # crude transaction cost model (roundtrip bps)
    cost = cfg.fee_bps_roundtrip / 10_000
    trade_rets = (rets[signal] - cost).dropna()

    if trade_rets.empty:
        return BacktestResult(0, 0.0, 0.0, 0.0)

    win_rate = float((trade_rets > 0).mean())
    avg_return = float(trade_rets.mean())
    cumulative_return = float((1.0 + trade_rets).prod() - 1.0)

    return BacktestResult(
        trades=int(trade_rets.shape[0]),
        win_rate=win_rate,
        avg_return=avg_return,
        cumulative_return=cumulative_return,
    )
