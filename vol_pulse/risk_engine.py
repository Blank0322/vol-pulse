from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskLimits:
    max_single_btc: float
    max_total_btc: float


@dataclass
class RiskReport:
    max_contracts: float
    est_margin_base: float
    est_margin_shock: float
    est_drawdown_usd: float


class RiskEngine:
    def __init__(self, account_balance: float, limits: RiskLimits) -> None:
        self.account_balance = account_balance
        self.limits = limits

    def max_contracts_allowed(self, open_contracts_btc: float = 0.0) -> float:
        remaining_total = max(self.limits.max_total_btc - open_contracts_btc, 0.0)
        return max(min(self.limits.max_single_btc, remaining_total), 0.0)

    def estimate_margin_and_drawdown(
        self,
        spot_price: float,
        strike: float,
        premium_btc: float,
        iv: float,
        contracts_btc: float,
    ) -> RiskReport:
        premium_usd = premium_btc * spot_price * contracts_btc
        base_margin = self._maintenance_margin(spot_price, strike, premium_btc, iv, contracts_btc)

        shock_iv = iv * 1.2
        shock_margin = self._maintenance_margin(spot_price, strike, premium_btc, shock_iv, contracts_btc)

        est_drawdown = min(base_margin - premium_usd, self.account_balance)
        return RiskReport(
            max_contracts=contracts_btc,
            est_margin_base=base_margin,
            est_margin_shock=shock_margin,
            est_drawdown_usd=est_drawdown,
        )

    @staticmethod
    def _maintenance_margin(
        spot_price: float,
        strike: float,
        premium_btc: float,
        iv: float,
        contracts_btc: float,
    ) -> float:
        # Simple approximation: risk component + premium, scaled by IV.
        intrinsic_buffer = max(strike - spot_price, 0.0) / spot_price
        risk_factor = 0.12 + 0.4 * iv + intrinsic_buffer
        margin_per_btc = spot_price * risk_factor + premium_btc * spot_price
        return margin_per_btc * contracts_btc
