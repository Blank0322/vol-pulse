# Backtest Notes

`vol_pulse.backtest` provides a minimal event-style backtest for the panic-vol regime.

## Inputs

CSV columns (hourly):
- `spot`
- `dvol`

## Signal

- price drop threshold over 1h
- dvol pulse threshold over 1h

## PnL proxy

The toy backtest currently uses a spot return proxy over a fixed holding window minus roundtrip fees.

This is intentionally simple and should be replaced by option-level payoff simulation in future iterations.

## Run

```bash
python scripts/run_backtest.py
python scripts/run_backtest.py --csv your_data.csv --hold-hours 24
```
