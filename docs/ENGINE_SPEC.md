# Vol-Pulse Engine Spec (Research Grade)

## Core thesis

Use VRP regression to estimate a fair short-vol premium baseline, then detect **2σ residual dislocations** with skew/term features.

## Signal stack

1. **Regime trigger**
   - spot drawdown + DVOL pulse
2. **Mispricing layer**
   - regress `vrp_t` on lagged `skew`, `term_spread`, `dvol`
   - flag `|residual_z| >= 2`
3. **Execution/risk layer**
   - dynamic hedge ratio from DVOL/skew/drawdown
   - risk interrupt (kill-switch) on extreme stress

## Current implementation in repo

- `vol_pulse/vrp_regression.py`
  - `fit_ols_signal(...)` returns expected VRP, residual, z-score, 2σ flag
- `vol_pulse/hedge_control.py`
  - `dynamic_hedge_ratio(...)`
  - `risk_interrupt(...)`

## Next upgrade

- Replace OLS with rolling robust regression (Huber/Lasso optional)
- Add option-level Greeks-aware hedge target
- Add event-log persistence + replay analytics
