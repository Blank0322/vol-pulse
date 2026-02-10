from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List


@dataclass
class MockMarketSnapshot:
    timestamp: float
    spot_price: float
    dvol: float
    realized_vol_24h: float
    options: List[dict]


class MockDataGenerator:
    def __init__(self, spot_price: float = 70000.0, dvol: float = 60.0) -> None:
        self.base_spot = spot_price
        self.base_dvol = dvol

    def make_panic_snapshot(self) -> MockMarketSnapshot:
        ts = time.time()
        spot = self.base_spot * 0.95
        dvol = self.base_dvol * 1.10
        options = self._mock_options(spot)
        return MockMarketSnapshot(
            timestamp=ts, spot_price=spot, dvol=dvol, realized_vol_24h=0.55, options=options
        )

    def _mock_options(self, spot: float) -> List[dict]:
        exp_ts = (time.time() + 21 * 86400) * 1000
        return [
            {
                "instrument_name": "BTC-TEST-85000-P",
                "strike": spot * 0.85,
                "option_type": "put",
                "expiration_timestamp": exp_ts,
                "delta": -0.18,
                "mark_iv": 0.75,
                "bid": 0.015,
                "ask": 0.017,
            },
            {
                "instrument_name": "BTC-TEST-90000-P",
                "strike": spot * 0.90,
                "option_type": "put",
                "expiration_timestamp": exp_ts,
                "delta": -0.22,
                "mark_iv": 0.70,
                "bid": 0.012,
                "ask": 0.014,
            },
        ]
