# Strategy Note (Vol-Pulse)

## Core idea

Target regime: **spot drawdown + implied vol pulse**.

When BTC sells off quickly and DVOL jumps, option premiums can temporarily overprice downside risk. The monitor flags this regime and ranks candidate contracts using:

- annualized premium yield
- safety margin (distance to strike)
- VRP-like proxy (IV vs realized vol)
- skew and term-structure diagnostics

## Notation (practical)

- `spot_chg_1h = spot_t / spot_{t-1} - 1`
- `dvol_chg_1h = dvol_t / dvol_{t-1} - 1`

Entry trigger (baseline):
- `spot_chg_1h <= -3%`
- `dvol_chg_1h >= +10%`

## Risk controls

- cap single-position notional
- cap total option exposure
- no blind fills under low-liquidity conditions
- explicit invalidation conditions in alerts

## Caveat

This is a monitoring / research scaffold, not production execution logic.
