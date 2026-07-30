"""LiveTradingRuntime — wires MT5 adapters + TIE pipeline for live/demo trading.
Entry point: receive market tick → run TIE → submit order if approved.
No trading logic here. Pure orchestration.
"""
import sys
import logging
from typing import Any, List, Optional

from adapters.broker.mt5_broker import MT5BrokerAdapter
from adapters.market.mt5_market import MT5MarketAdapter
from adapters.hck_bridge import HCKBridge
from runtime.compiler_bridge import CompilerBridge
from runtime.execution_runtime import ExecutionRuntime
from runtime.execution_service import ExecutionService
from runtime.execution_result import ExecutionResult
from runtime.context_builder import ExecutionContext
from core.rules.risk.risk_registry import build_risk_registry

log = logging.getLogger("LiveTradingRuntime")


class LiveTradingRuntime:
    """
    Full live trading pipeline:
    Market tick → CompilerBridge → RiskGate → ExecutionService → MT5
    """

    def __init__(
        self,
        gateway_url: str,
        gateway_token: str,
        setup_definitions: List[dict],
        symbols: List[str],
        hck_bridge: Optional[HCKBridge] = None,
        risk_overrides: Optional[dict] = None,
        canonical_id: str = "boskuh",
    ):
        self._canonical_id = canonical_id
        self._symbols = symbols

        # Broker adapter (real MT5)
        self._broker = MT5BrokerAdapter(gateway_url, gateway_token)

        # Market adapter (polling)
        self._market = MT5MarketAdapter(gateway_url, gateway_token, poll_interval=1.0)
        self._market.set_on_tick(self._on_tick)

        # TIE compiler
        self._compiler = CompilerBridge(
            setup_definitions=setup_definitions,
            hck_bridge=hck_bridge,
        )

        # Risk gate
        risk_registry = build_risk_registry(overrides=risk_overrides or {})

        # Execution service
        exec_runtime = ExecutionRuntime(broker_adapter=self._broker)
        self._service = ExecutionService(
            execution_runtime=exec_runtime,
            risk_registry=risk_registry,
            hck_bridge=hck_bridge,
        )

        self._running = False

    def initialize(self) -> None:
        self._broker.initialize()
        self._broker.connect()
        self._market.initialize()
        self._market.connect()
        log.info("LiveTradingRuntime initialized")

    def start(self) -> None:
        self._running = True
        for sym in self._symbols:
            self._market.subscribe(sym)
        log.info(f"LiveTradingRuntime started, subscribed: {self._symbols}")

    def stop(self) -> None:
        self._running = False
        self._market.disconnect()
        self._broker.disconnect()
        log.info("LiveTradingRuntime stopped")

    def health(self) -> dict:
        return {
            "broker": self._broker.health_check(),
            "market": self._market.health_check(),
            "running": self._running,
        }

    def _on_tick(self, symbol: str, tick: dict) -> None:
        if not self._running:
            return
        snapshot = self._market.get_market_snapshot(symbol)
        if not snapshot:
            return
        account = self._broker.get_account_info()
        ctx = ExecutionContext(
            market={
                "symbol": symbol,
                "trend": "unknown",  # set by MarketBrain/Context migration
                "session": "open",
                "atr": float(snapshot.spread) * 2,
                "spread": float(snapshot.spread),
                "market_status": "open",
                "current_price": float(snapshot.last_price),
            },
            memory={},
            metadata={"canonical_id": self._canonical_id, "symbol": symbol},
        )
        decision = self._compiler.compile(ctx)
        if decision.action in ("WAIT", "SKIP"):
            return

        from core.execution.execution_contract import ExecutionContract
        contract = ExecutionContract(
            symbol=symbol,
            action=decision.action,
            direction=decision.action,
            confidence=float(decision.confidence or 0),
            setup=str(getattr(decision, "setup_id", "")),
            methodology="bystra",
            entry_pattern="",
            reason=decision.reason or "",
            metadata={
                "volume": 0.01,
                "canonical_id": self._canonical_id,
            },
        )
        context = {
            "spread": float(snapshot.spread),
            "lot": 0.01,
            "equity": account.equity,
            "peak_balance": account.balance,
            "daily_pnl": 0.0,
            "news_events": [],
            "canonical_id": self._canonical_id,
        }
        result: ExecutionResult = self._service.submit(contract, context=context)
        if result.success:
            log.info(f"Order filled: {symbol} {decision.action} @ {result.filled_price}")
        else:
            log.info(f"Order skipped/rejected: {result.status} — {result.error}")
