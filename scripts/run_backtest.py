from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

# Allow running as a plain script from repo root without installing the package.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from vol_pulse.backtest import BacktestConfig, run_backtest


def build_mock_df(n: int = 300) -> pd.DataFrame:
    # deterministic-ish synthetic series
    import math

    rows = []
    spot = 65000.0
    dvol = 45.0
    for i in range(n):
        # slow drift + periodic mini shocks
        spot *= 1 + (0.0002 * math.sin(i / 12.0))
        dvol *= 1 + (0.0008 * math.cos(i / 11.0))

        if i % 72 == 0 and i > 0:
            spot *= 0.96
            dvol *= 1.18

        rows.append({"spot": spot, "dvol": dvol})
    return pd.DataFrame(rows)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", help="Optional csv path with columns: spot,dvol")
    p.add_argument("--hold-hours", type=int, default=24)
    args = p.parse_args()

    if args.csv:
        df = pd.read_csv(args.csv)
    else:
        df = build_mock_df()

    cfg = BacktestConfig(hold_hours=args.hold_hours)
    res = run_backtest(df, cfg)

    print("Backtest result")
    print(f"- trades: {res.trades}")
    print(f"- win_rate: {res.win_rate:.2%}")
    print(f"- avg_return: {res.avg_return:.2%}")
    print(f"- cumulative_return: {res.cumulative_return:.2%}")


if __name__ == "__main__":
    main()
