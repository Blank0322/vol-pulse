# Vol-Pulse

A lightweight BTC options monitoring toolkit focused on **volatility pulses** (e.g. DVOL spikes) and the **volatility risk premium (VRP)**.

Goal: turn a messy "watch + react" workflow into a small, traceable pipeline.

## What it does

- Pulls DVOL + spot + option chain (Deribit)
- Computes VRP proxies and simple IV percentile/rank metrics
- Tracks skew/term structure signals
- Emits an "entry alert" when the market transitions from *slow bleed* → *panic + IV expansion*

## Architecture

```text
Deribit → Snapshot → Metrics → Signal Rules → Candidate Scan → Risk Checks → Alert
```

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m vol_pulse.monitor --mock --verbose
```

> Notes
> - This repo is an engineering/analysis scaffold, not trading advice.
> - Put API keys in `.env` (see `.env.example`).
