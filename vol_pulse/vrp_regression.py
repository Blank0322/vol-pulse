from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RegressionSignal:
    expected_vrp: float
    residual: float
    residual_z: float
    is_2sigma_mispricing: bool


def build_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Build regression features for VRP expectation.

    Required columns:
    - dvol (implied vol proxy)
    - realized_vol (realized vol proxy)
    - skew (put-call skew proxy)
    - term_spread (near-far IV spread)
    """
    d = df.copy()
    d["vrp"] = d["dvol"] - d["realized_vol"]
    d["skew_l1"] = d["skew"].shift(1)
    d["term_l1"] = d["term_spread"].shift(1)
    d["dvol_l1"] = d["dvol"].shift(1)
    d = d.dropna().reset_index(drop=True)
    return d


def fit_ols_signal(df: pd.DataFrame, lookback: int = 120) -> RegressionSignal | None:
    d = build_feature_frame(df)
    if len(d) < max(30, lookback):
        return None

    sub = d.iloc[-lookback:].copy()
    y = sub["vrp"].to_numpy(dtype=float)
    x = sub[["skew_l1", "term_l1", "dvol_l1"]].to_numpy(dtype=float)

    # add intercept
    X = np.column_stack([np.ones(len(x)), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)

    y_hat = X @ beta
    resid = y - y_hat
    resid_std = np.std(resid, ddof=1) if len(resid) > 2 else 0.0

    expected_vrp = float(y_hat[-1])
    last_resid = float(resid[-1])
    z = float(last_resid / resid_std) if resid_std > 1e-12 else 0.0

    return RegressionSignal(
        expected_vrp=expected_vrp,
        residual=last_resid,
        residual_z=z,
        is_2sigma_mispricing=abs(z) >= 2.0,
    )
