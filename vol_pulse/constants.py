ACCOUNT_BALANCE = 22000
MAX_NOTIONAL_LIMIT = 0.25  # BTC

# Option scan universe: 14-30 DTE, put delta in [0.15, 0.20]
TARGET_DELTA = (0.15, 0.20)
OPTION_DTE_RANGE_DAYS = (14, 30)

# Entry rule
ENTRY_PRICE_DROP_1H = -0.025  # <= -2.5%
MIN_DVOL_PULSE = 0.05  # >= +5%
ENTRY_IVP_THRESHOLD = 70.0
ENTRY_IVR_THRESHOLD = 50.0

# Slow-bleed trap rule
SLOW_BLEED_PRICE_DROP_1H = -0.02  # <= -2.0%
SLOW_BLEED_DVOL_MAX_1H = 0.0      # DVOL flat/down

LOOKBACK_PERIOD = 365  # days for IVR/IVP history

DERIBIT_BASE_URL = "https://www.deribit.com/api/v2"
BTC_INDEX_NAME = "btc_usd"
DVOL_SYMBOL = "DVOL"
