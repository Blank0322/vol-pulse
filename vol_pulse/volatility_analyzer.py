from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Iterable, List, Tuple

import numpy as np


@dataclass
class IVMetrics:
    ivr: float | None
    ivp: float | None
    dvol_slope: float | None


class VolatilityAnalyzer:
    def __init__(self, lookback_days: int = 365, dvol_window_hours: int = 24) -> None:
        self.lookback_days = lookback_days
        self.dvol_window_seconds = dvol_window_hours * 3600
        self._dvol_points: Deque[Tuple[float, float]] = deque()
        self._dvol_history: List[float] = []

    def set_dvol_history(self, dvol_values: Iterable[float]) -> None:
        values = [float(v) for v in dvol_values if v is not None]
        self._dvol_history = values[-self.lookback_days :]

    def add_dvol_point(self, timestamp: float, dvol: float) -> None:
        self._dvol_points.append((timestamp, float(dvol)))
        self._trim_window(timestamp)

    def add_dvol_now(self, dvol: float) -> None:
        self.add_dvol_point(time.time(), dvol)

    def _trim_window(self, now_ts: float) -> None:
        cutoff = now_ts - self.dvol_window_seconds
        while self._dvol_points and self._dvol_points[0][0] < cutoff:
            self._dvol_points.popleft()

    def compute_metrics(self, current_dvol: float | None = None) -> IVMetrics:
        if current_dvol is None and self._dvol_points:
            current_dvol = self._dvol_points[-1][1]

        ivr = self._compute_ivr(current_dvol)
        ivp = self._compute_ivp(current_dvol)
        slope = self._compute_dvol_slope()
        return IVMetrics(ivr=ivr, ivp=ivp, dvol_slope=slope)

    def _compute_ivr(self, current_dvol: float | None) -> float | None:
        if current_dvol is None or not self._dvol_history:
            return None
        dvol_min = min(self._dvol_history)
        dvol_max = max(self._dvol_history)
        if dvol_max == dvol_min:
            return 0.0
        ivr = (current_dvol - dvol_min) / (dvol_max - dvol_min) * 100.0
        return float(min(max(ivr, 0.0), 100.0))

    def _compute_ivp(self, current_dvol: float | None) -> float | None:
        if current_dvol is None or not self._dvol_history:
            return None

        arr = np.sort(np.asarray(self._dvol_history, dtype=np.float64))
        n = arr.size
        left = int(np.searchsorted(arr, current_dvol, side="left"))
        right = int(np.searchsorted(arr, current_dvol, side="right"))
        if right == left:
            rank = right
        else:
            rank = (left + 1 + right) / 2.0
        return float(rank / n * 100.0)

    def _compute_dvol_slope(self) -> float | None:
        if len(self._dvol_points) < 2:
            return None
        xs = np.array([t for t, _ in self._dvol_points], dtype=np.float64)
        ys = np.array([v for _, v in self._dvol_points], dtype=np.float64)
        xs = xs - xs[0]
        if xs[-1] == 0:
            return 0.0
        slope, _ = np.polyfit(xs, ys, 1)
        return float(slope)
