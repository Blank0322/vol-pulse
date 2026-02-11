# Vol-Pulse

BTC options monitoring + strategy-research scaffold.

Focus: detect **panic-vol regimes** (spot drawdown + DVOL expansion), then evaluate candidate setup quality and risk bounds.

## Scope

- **Execution side (monitoring)**: live signal detection + alert payload
- **Research side (backtest)**: quick event-style sanity checks before going deeper

## Architecture

```text
Market Data -> Metrics (IVP/IVR, VRP proxy, skew, term) -> Signal Rules -> Candidate Scan -> Risk Checks -> Alert
                                            |
                                            +-> Backtest harness
```

## Repo map

- `vol_pulse/` core package
  - `monitor.py` package entrypoint
  - `main.py` monitor loop
  - `opportunity_scanner.py` candidate ranking and structure diagnostics
  - `risk_engine.py` notional / margin guardrails
  - `backtest.py` minimal event-style backtest
  - `vrp_regression.py` VRP regression + 2σ mispricing signal
  - `hedge_control.py` dynamic hedge ratio + risk interrupt rules
- `scripts/run_backtest.py` standalone backtest runner
- `docs/STRATEGY.md` strategy note
- `docs/BACKTEST.md` backtest assumptions and usage
- `docs/ENGINE_SPEC.md` research-grade engine spec

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m vol_pulse.monitor --mock --verbose
```

## Backtest quick run

```bash
python scripts/run_backtest.py
```

## Disclaimer

For research / monitoring only. Not financial advice.
