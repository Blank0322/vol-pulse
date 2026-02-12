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

Entry trigger (current spec, all must hold):
- `spot_chg_1h <= -2.5%`
- `dvol_chg_1h >= +5%`
- `IVP > 70` OR `IVR > 50` (based on 365-day DVOL history)

Slow-bleed trap (block Sell Put scan this cycle):
- `spot_chg_1h <= -2%`
- `dvol_chg_1h <= 0%`

Option scan universe:
- DTE in `[14, 30]` days
- Put only
- `abs(delta) in [0.15, 0.20]`

## Risk controls

- cap single-position notional
- cap total option exposure
- no blind fills under low-liquidity conditions
- explicit invalidation conditions in alerts

## Caveat

This is a monitoring / research scaffold, not production execution logic.
