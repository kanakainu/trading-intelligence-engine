#!/usr/bin/env python3
"""TIE v2 Production Runtime — New Architecture Pipeline.

Market Feed
→ Feature Engine
→ Regime Engine
→ Opportunity Engine
→ Detectors
→ Signal Contract
→ Signal Fusion
→ Trade Planner
→ Risk Gate
→ Entry Monitor
→ Trade Lifecycle
→ Learning Engine
"""
import sys
import time
import logging
from datetime import datetime, timezone

sys.path.insert(0, '/home/ubuntu/.hermes/trading')
sys.path.insert(0, '/home/ubuntu/trading-intelligence-engine')

# Gateway & Broker
from gateway_client import MT5GatewayClient
from adapters.broker.mt5_broker import MT5BrokerAdapter

# Core Engines (new)
from core.features import compute_features, FeatureInputs, get_feature_cache
from core.regime import classify_regime, RegimeInputs
from core.opportunity import evaluate_opportunity, OpportunityInputs
from core.signals import Signal, Direction
from core.fusion import fuse_signals, FusionInputs
from core.planner import build_trade_plan, PlannerInputs
from core.lifecycle import get_trade_lifecycle, LifecycleState
from core.learning import get_learning_engine, TradeOutcome, ExitReason

# Legacy (to be replaced)
from strategy.orchestrator import StrategyOrchestrator
from runtime.entry_monitor import EntryMonitor
from runtime.position_monitor import PositionMonitor
from runtime.position_state import PositionState
from core.rules.risk.risk_registry import build_risk_registry
from core.rules.plugins.plugin_interface import RuleResult
from reasoning.llm_reasoner import LLMReasoner

# Dashboard
from core.context.context_engine import ContextEngine
from detectors.common import find_swing_pivots, find_nearest_support, find_nearest_resistance, sl_buffer

# NEW: ScanContext
from core.context.scan_context import ScanContext, ScanInputs

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(message)s')
log = logging.getLogger("TIE_v2_Production")

URL = 'https://chips-extension-extensions-wearing.trycloudflare.com'
TOKEN = 'Jojo_56790@_000tUi_OO9'
SYMBOLS = ['XAUUSD', 'BTCUSD', 'GBPJPY']

_seen_setups = {}  # {(sym, setup_name, direction): timestamp} — dedup 5 min
DEDUP_WINDOW = 300  # seconds

# Initialize components
client = MT5GatewayClient(URL, TOKEN)
broker = MT5BrokerAdapter(base_url=URL, token=TOKEN)
broker.initialize()

# Legacy orchestrator (transition)
orc = StrategyOrchestrator(min_confidence=0.55)
monitor = EntryMonitor(broker=broker, gateway=client)
pos_monitor = PositionMonitor()
risk_gate = build_risk_registry()
context_engine = ContextEngine()

# New engines
feature_cache = get_feature_cache()
trade_lifecycle = get_trade_lifecycle()
learning_engine = get_learning_engine()

log.info(f"TIE v2 Production started: {SYMBOLS}. Risk Gate active.")

# Benchmark storage
benchmark_data = {
    "loop_times": [],
    "feature_times": [],
    "regime_times": [],
    "opportunity_times": [],
    "detector_times": [],
    "fusion_times": [],
    "planner_times": [],
    "gateway_times": [],
}


def _compute_real_sr(candles_h1: list, price: float = 0.0) -> dict:
    if not candles_h1:
        return {"h1_support": 0.0, "h1_resistance": 999999.0}
    support = find_nearest_support(candles_h1, price) if price else 0.0
    resistance = find_nearest_resistance(candles_h1, price) if price else 999999.0
    if not support or not resistance:
        pivots = find_swing_pivots(candles_h1, n=2)
        highs = [p["price"] for p in pivots if p["type"] == "high"]
        lows = [p["price"] for p in pivots if p["type"] == "low"]
        if not support:
            support = max(lows) if lows else 0.0
        if not resistance:
            resistance = min(highs) if highs else 999999.0
    return {"h1_support": support, "h1_resistance": resistance}


def _get_spread(client, symbol: str) -> float:
    try:
        price_data = client.price(symbol)
        return float(price_data.get("spread", 0))
    except Exception:
        return 10.0


def build_scan_context(
    symbol: str,
    candles: dict,
    current_price: float,
    spread: float,
    balance: float,
    equity: float,
    open_positions: int,
    raw_positions: list,
    scan_id: str
) -> ScanContext:
    """Build complete ScanContext from raw data."""
    loop_start = time.perf_counter()
    
    # 1. Feature Engine
    feat_start = time.perf_counter()
    feat_inputs = FeatureInputs(
        candles=candles,
        spread=spread,
        symbol=symbol,
        timestamp=datetime.now(timezone.utc),
        current_price=current_price
    )
    features = compute_features(feat_inputs)
    benchmark_data["feature_times"].append(time.perf_counter() - feat_start)
    
    # 2. Regime Engine
    regime_start = time.perf_counter()
    regime_inputs = RegimeInputs(
        ema=features.ema,
        ema_slope=features.ema_slope,
        atr=features.atr,
        atr_percent=features.atr_percent,
        true_range=features.true_range,
        vwap=features.vwap,
        distance_to_vwap=features.distance_to_vwap,
        volume_ratio=features.volume_ratio,
        volume_spike=features.volume_spike,
        momentum_score=features.momentum_score,
        spread=features.spread,
        tick_speed=features.tick_speed,
        price_velocity=features.price_velocity,
        symbol=symbol,
        timeframe="H1",
        current_price=current_price,
        scan_id=scan_id
    )
    regime = classify_regime(regime_inputs)
    benchmark_data["regime_times"].append(time.perf_counter() - regime_start)
    
    # 3. Opportunity Engine
    opp_start = time.perf_counter()
    opp_inputs = OpportunityInputs(
        spread=spread,
        atr_percent=features.atr_percent.get("H1", 0.0),
        volume_ratio=features.volume_ratio.get("H1", 1.0),
        regime_name=regime.regime.name,
        adx=regime.adx,
        current_time=datetime.now(timezone.utc),
        symbol=symbol,
        scan_id=scan_id
    )
    opportunity = evaluate_opportunity(opp_inputs)
    benchmark_data["opportunity_times"].append(time.perf_counter() - opp_start)
    
    # 4. MarketContext (for legacy compatibility)
    sr = _compute_real_sr(candles.get("H1", []), current_price)
    market = MarketContext(symbol=symbol, timestamp=datetime.now(timezone.utc))
    spread_buf_val = sl_buffer(market)
    market.metadata.update({
        "candles": candles,
        "current_price": current_price,
        "atr": context_engine._calc_atr(candles.get("H1", [])),
        "h1_support": sr["h1_support"],
        "h1_resistance": sr["h1_resistance"],
        "h1_trend": "bearish" if candles["H1"][-1]['close'] < candles["H1"][-5]['close'] else "bullish",
        "nearest_support": sr["h1_support"],
        "nearest_resistance": sr["h1_resistance"],
        "spread": spread,
        "spread_buffer": spread_buf_val,
        "balance": balance,
        "equity": equity,
        "open_positions": len(raw_positions),
    })
    
    # 5. ScanContext
    scan_ctx = ScanContext(
        market=market,
        features=features,
        regime=regime,
        opportunity=opportunity,
        scan_id=scan_id,
        timestamp=datetime.now(timezone.utc)
    )
    
    return scan_ctx


def run_new_pipeline(scan_ctx: ScanContext) -> list:
    """Run new detector → signal → fusion → planner pipeline."""
    if not scan_ctx.is_opportunity_allowed():
        return []
    
    symbol = scan_ctx.symbol
    
    # 6. Detectors (legacy for now, migrate one by one)
    det_start = time.perf_counter()
    facts = orc.run(scan_ctx.market)  # Uses legacy MarketContext for now
    benchmark_data["detector_times"].append(time.perf_counter() - det_start)
    
    if not facts:
        return []
    
    # Convert Facts → Signals
    signals = []
    for fact in facts:
        direction = Direction.BUY if fact.metadata.get("direction") == "BUY" else Direction.SELL
        entry_zone = fact.metadata.get("entry_zone", {"low": 0.0, "high": 0.0})
        
        sig = Signal(
            signal_id=f"{fact.metadata.get('detector_name', 'UNK')}_{symbol}_{int(time.time())}",
            strategy=fact.metadata.get("detector_name", "UNKNOWN"),
            symbol=symbol,
            direction=direction,
            entry_zone=entry_zone,
            confidence=fact.confidence,
            timeframe=fact.metadata.get("entry_tf", "M5"),
            regime=scan_ctx.get_regime_name(),
            opportunity_priority=scan_ctx.get_opportunity_priority(),
            metadata={
                "detector": fact.metadata.get("detector_name", "UNKNOWN"),
                "base_zone": [entry_zone.get("low", 0), entry_zone.get("high", 0)]
            }
        )
        signals.append(sig)
    
    # 7. Signal Fusion
    fusion_start = time.perf_counter()
    fusion_inputs = FusionInputs(
        signals=signals,
        symbol=symbol,
        scan_id=scan_ctx.scan_id,
        timestamp=datetime.now(timezone.utc)
    )
    fused = fuse_signals(fusion_inputs)
    benchmark_data["fusion_times"].append(time.perf_counter() - fusion_start)
    
    # Skip if conflict or no signals
    if fused.decision.value in ("conflict", "no_signals"):
        log.info(f"Fusion {fused.decision.value} for {symbol}")
        return []
    
    # 8. Trade Planner
    plan_start = time.perf_counter()
    plan_inputs = PlannerInputs(
        symbol=symbol,
        direction=fused.direction,
        entry_zone=fused.entry_zone,
        confidence=fused.confidence,
        strategies=fused.strategies,
        timeframe="M5",  # Use primary TF
        h1_support=scan_ctx.h1_support,
        h1_resistance=scan_ctx.h1_resistance,
        detector_danger_zone=fused.metadata.get("danger_zone"),
        detector_sl=None,
        candles=scan_ctx.candles,
        spread_buffer=scan_ctx.market.metadata.get("spread_buffer", 0.5),
        atr=scan_ctx.atr,
        balance=scan_ctx.market.metadata.get("balance", 1000.0),
        risk_per_trade_pct=1.0,
        scan_id=scan_ctx.scan_id
    )
    plan = build_trade_plan(plan_inputs)
    benchmark_data["planner_times"].append(time.perf_counter() - plan_start)
    
    # Return plan for risk gate
    return [plan]


def run_benchmark_log():
    """Log benchmark statistics."""
    import statistics
    
    def stats(name, times):
        if not times:
            return
        log.info(f"BENCHMARK {name}: count={len(times)}, avg={statistics.mean(times)*1000:.2f}ms, "
                 f"max={max(times)*1000:.2f}ms, median={statistics.median(times)*1000:.2f}ms")
    
    for name, times in benchmark_data.items():
        stats(name, times)


while True:
    loop_start = time.perf_counter()
    
    for sym in SYMBOLS:
        try:
            log.info(f"--- Scanning {sym} ---")
            
            # Fetch candles
            gw_start = time.perf_counter()
            candles = {}
            for tf in ["M5", "M15", "M30", "H1"]:
                count = 40 if tf == "M5" else 20
                candles[tf] = client.candles(sym, tf, count)
            
            price_data = client.price(sym)
            price = price_data['ask']
            spread = _get_spread(client, sym)
            
            account_info = client.account() or {}
            raw_positions = client.positions() or []
            balance = float(account_info.get("balance", 0))
            equity = float(account_info.get("equity", balance))
            
            benchmark_data["gateway_times"].append(time.perf_counter() - gw_start)
            
            # Position state monitoring
            pos_states = [PositionState(
                position_id=str(p.get("ticket")),
                symbol=p.get("symbol"),
                direction=p.get("type", "").upper(),
                entry_price=p.get("price_open", 0),
                current_price=price if p.get("symbol") == sym else p.get("price_current", 0),
                stop_loss=p.get("sl"),
                take_profit=p.get("tp"),
                volume=p.get("volume", 0)
            ) for p in raw_positions]
            
            # SL/TP Hit Notification
            from runtime.telegram_notifier import TelegramNotifier
            notifier = TelegramNotifier(TOKEN)
            
            for ps in pos_states:
                if ps.symbol != sym:
                    continue
                profit = ps.profit_pts * ps.volume * 100
                if ps.stop_loss:
                    hit = (ps.is_buy and price <= ps.stop_loss) or (not ps.is_buy and price >= ps.stop_loss)
                    # NOTIF OFF
                if ps.take_profit:
                    hit = (ps.is_buy and price >= ps.take_profit) or (not ps.is_buy and price <= ps.take_profit)
                    # NOTIF OFF
            
            # Build ScanContext
            scan_id = f"scan_{sym}_{int(time.time())}"
            scan_ctx = build_scan_context(
                symbol=sym,
                candles=candles,
                current_price=price,
                spread=spread,
                balance=balance,
                equity=equity,
                open_positions=len(raw_positions),
                raw_positions=raw_positions,
                scan_id=scan_id
            )
            
            # Run new pipeline
            plans = run_new_pipeline(scan_ctx)
            
            # Legacy decision path (parallel for comparison)
            decision = orc.best_decision(scan_ctx.market)
            
            if decision.action != "WAIT":
                log.info(f"Setup detected: {decision.setup_name} {decision.action} conf={decision.confidence:.0%}")
                
                risk_ctx = {
                    "symbol": sym,
                    "entry": (decision.metadata.get("entry_zone") or {}).get("high"),
                    "sl": decision.metadata.get("sl"),
                    "tp": decision.metadata.get("take_profit"),
                    "direction": decision.action,
                    "confidence": decision.confidence,
                    "spread": spread,
                    "balance": balance,
                    "equity": equity,
                    "open_positions": len(raw_positions),
                    "lot": 0.01,
                    "sl_pips": 0,
                    "time": time.time(),
                }
                
                if risk_ctx["sl"] and risk_ctx["entry"]:
                    risk_ctx["sl_pips"] = abs(risk_ctx["entry"] - risk_ctx["sl"]) * 10
                if sym in ("BTCUSD", "ETHUSD"):
                    risk_ctx["sl_pips"] = 0
                
                risk_results = {}
                for rule_name in risk_gate.list_enabled():
                    plugin = risk_gate.get(rule_name)
                    if plugin:
                        risk_results[rule_name] = plugin.evaluate(risk_ctx, {}, decision)
                
                if all(r.status == "APPROVE" for r in risk_results.values()):
                    dedup_key = (sym, decision.setup_name, decision.action)
                    now = time.time()
                    last_seen = _seen_setups.get(dedup_key, 0.0)
                    if now - last_seen < DEDUP_WINDOW:
                        log.info(f"Dedup: skip {decision.setup_name} {decision.action} {sym} (seen {(now-last_seen):.0f}s ago)")
                    else:
                        _seen_setups[dedup_key] = now
                        log.info(f"Risk Gate: ✅ PASS — {sym}")
                        
                        # Push to HCK
                        from runtime.hck_wire import push_decision
                        push_decision(decision)
                        monitor.add_setup(decision)
                else:
                    reasons = "; ".join(f"{n}={r.status}:{r.reason}" for n, r in risk_results.items() if r.status != "APPROVE")
                    log.info(f"Risk Gate: ❌ BLOCKED {sym}. {reasons}")
            else:
                log.info(f"No setup for {sym} (WAIT)")
            
            # Position monitoring
            market_update = {
                sym: {
                    "price": price,
                    "atr": scan_ctx.market.metadata.get("atr", 0.0),
                    "candles": candles
                }
            }
            
            contracts = {}
            for ps in pos_states:
                if ps.symbol == sym:
                    contracts[ps.position_id] = type('Contract', (), {
                        'metadata': {
                            'be_trigger_atr': 1.0,
                            'trail_trigger_atr': 1.5,
                            'trail_offset_atr': 0.5,
                            'partial_tp_pct': 0.5,
                            'early_exit_reversal': True,
                        }
                    })()
            
            if contracts:
                pos_monitor.tick(pos_states, contracts, market_update)
            
            # Trade Lifecycle update
            for ps in pos_states:
                if ps.symbol == sym and ps.volume > 0:
                    lifecycle_pos = trade_lifecycle.get(ps.position_id)
                    if not lifecycle_pos:
                        trade_lifecycle.create_position(
                            position_id=ps.position_id,
                            symbol=ps.symbol,
                            direction=ps.direction.lower(),
                            current_price=price,
                            volume=ps.volume,
                            volume_remaining=ps.volume,
                            floating_pl=ps.profit_pts * ps.volume * 100,
                            realized_pl=0.0,
                            sl=ps.stop_loss,
                            tp=ps.take_profit,
                            danger_zone=scan_ctx.h1_support if ps.direction == "BUY" else scan_ctx.h1_resistance,
                            entry_price=ps.entry_price,
                            opened_at=datetime.now(timezone.utc),
                            closed_at=None,
                            duration_seconds=0.0
                        )
                    else:
                        # Update existing
                        trade_lifecycle.update_state(
                            ps.position_id,
                            LifecycleState.OPEN,
                            trigger="price",
                            current_price=price,
                            floating_pl=ps.profit_pts * ps.volume * 100
                        )
            
            # Dashboard status write
            import json, os
            status_path = "/home/ubuntu/tie-dashboard/data/tie_status.json"
            
            all_pairs_data = {}
            if os.path.exists(status_path):
                try:
                    with open(status_path, "r") as f:
                        existing = json.load(f)
                        if "pairs" in existing:
                            all_pairs_data = existing["pairs"]
                except:
                    all_pairs_data = {}
            
            pair_data = {
                "price": price,
                "support": scan_ctx.h1_support,
                "resistance": scan_ctx.h1_resistance,
                "trend": scan_ctx.market.metadata.get("h1_trend", "neutral"),
                "regime": scan_ctx.get_regime_name(),
                "spread": spread,
                "atr": scan_ctx.atr,
                "session": scan_ctx.market.metadata.get("h1_trend", "ASIA").upper(),
                "last_scan": datetime.now(timezone.utc).isoformat(),
                "setup": None
            }
            
            if decision.action != "WAIT":
                pair_data["setup"] = {
                    "name": decision.setup_name,
                    "direction": decision.action,
                    "confidence": decision.confidence,
                    "entry_zone": decision.metadata.get("entry_zone"),
                    "sl": decision.metadata.get("sl"),
                    "tp": decision.metadata.get("take_profit"),
                    "danger_zone": decision.metadata.get("danger_zone"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            
            all_pairs_data[sym] = pair_data
            
            status_data = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "balance": balance,
                "equity": equity,
                "floating_pnl": sum(p.profit_pts * p.volume for p in pos_states),
                "margin_percent": 0.0,
                "pairs": all_pairs_data,
                "positions": [{"side": p.direction, "volume": p.volume, "entry": p.entry_price, "sl": p.stop_loss, "tp": p.take_profit, "pnl": p.profit_pts * p.volume, "symbol": p.symbol} for p in pos_states],
                "total_setups": sum(1 for p in all_pairs_data.values() if p.get("setup")),
            }
            
            os.makedirs(os.path.dirname(status_path), exist_ok=True)
            with open(status_path, "w") as f:
                json.dump(status_data, f)
            
            monitor.update()
            
        except Exception as e:
            log.error(f"Error scanning {sym}: {e}")
    
    # Benchmark logging every 100 loops
    benchmark_data["loop_times"].append(time.perf_counter() - loop_start)
    if len(benchmark_data["loop_times"]) % 100 == 0:
        run_benchmark_log()
    
    time.sleep(10)