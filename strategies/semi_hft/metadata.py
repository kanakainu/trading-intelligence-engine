from dataclasses import dataclass

@dataclass
class StrategyMetadata:
    name: str
    version: str
    symbols: list

SEMI_HFT_METADATA = StrategyMetadata(name="SemiHFT", version="1.0", symbols=["XAUUSD"])
