"""Phase 4 Compatibility Layer — boundary, versioning, migration guards, adapter stubs.
Phase 3 modules untouched.
"""

TIE_VERSION = "3.0.0"   # Phase 3 output version
PHASE4_VERSION = "4.0.0"  # Current layer version

SUPPORTED_ADAPTER_TARGETS = frozenset([
    "mt5", "ctrader", "binance", "tradingview", "rest_api", "cli",
])
