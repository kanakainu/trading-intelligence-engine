#!/usr/bin/env python3
"""TIE Production Runtime — Multi-Symbol Support (XAUUSD, BTCUSD, GBPUSD)."""
import sys, time, logging
from datetime import datetime, timezone
sys.path.insert(0, '/home/ubuntu/.hermes/trading')
sys.path.insert(0, '/home/ubuntu/trading-intelligence-engine')

from gateway_client import MT5GatewayClient
from core.context.context_model import MarketContext
from strategy.orchestrator import StrategyOrchestrator
from runtime.entry_monitor import EntryMonitor
from runtime.position_monitor import PositionMonitor
from runtime.position_state import PositionState
from adapters.broker.mt5_broker import MT5BrokerAdapter
from runtime.hck_wire import push_decision
from core.rules.risk.risk_registry import build_risk_registry
from core.rules.plugins.plugin_interface import RuleResult
from detectors.common import find_swing_pivots, find_nearest_support, find_nearest_resistance, sl_buffer
from core.context.context_engine import ContextEngine
from reasoning.llm_reasoner import LLMReasoner

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(message)s')
log = logging.getLogger("TIE_Production")

URL = 'https://chips-extension-extensions-wearing.trycloudflare.com'
TOKEN = 'Jojo_56790@_000tUi_OO9'
SYMBOLS = ['XAUUSD', 'BTCUSD', 'GBPJPY']

_seen_setups = {}  # {(sym, setup_name, direction): timestamp} — dedup 5 min
DEDUP_WINDOW = 300  # seconds

client = MT5GatewayClient(URL, TOKEN)
broker = MT5BrokerAdapter(base_url=URL, token=TOKEN)
broker.initialize()

orc = StrategyOrchestrator(min_confidence=0.55)
monitor = EntryMonitor(broker=broker, gateway=client)
pos_monitor = PositionMonitor()
risk_gate = build_risk_registry()
context_engine = ContextEngine()

log.info(f"TIE Production Multi-Symbol started: {SYMBOLS}. Risk Gate active.")

# D2 shadow runtime — initialized once, reused every scan
class _MSRState: pass
_msr_runtime = _MSRState()

def _compute_real_sr(candles_h1: list, price: float = 0.0) -> dict:
    if not candles_h1: return {"h1_support": 0.0, "h1_resistance": 999999.0}
    support = find_nearest_support(candles_h1, price) if price else 0.0
    resistance = find_nearest_resistance(candles_h1, price) if price else 999999.0
    if not support or not resistance:
        pivots = find_swing_pivots(candles_h1, n=2)
        highs = [p["price"] for p in pivots if p["type"] == "high"]
        lows  = [p["price"] for p in pivots if p["type"] == "low"]
        if not support:    support    = max(lows)  if lows  else 0.0
        if not resistance: resistance = min(highs) if highs else 999999.0
    return {"h1_support": support, "h1_resistance": resistance}

def _get_spread(client, symbol: str) -> float:
    try:
        price_data = client.price(symbol)
        return float(price_data.get("spread", 0))
    except Exception: return 10.0

while True:
    all_pairs_data = {}  # Accumulate ALL pairs per loop
    status_path = "/home/ubuntu/tie-dashboard/data/tie_status.json"
    
    for sym in SYMBOLS:
        try:
            log.info(f"--- Scanning {sym} ---")
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
            
            # SL/TP Hit Notification
            from runtime.telegram_notifier import TelegramNotifier
            notifier = TelegramNotifier(TOKEN)
            
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
            
            for ps in pos_states:
                if ps.symbol != sym: continue
                profit = ps.profit_pts * ps.volume * 100
                if ps.stop_loss:
                    hit = (ps.is_buy and price <= ps.stop_loss) or (not ps.is_buy and price >= ps.stop_loss)
                    # NOTIF OFF: if hit: notifier.notify_sl_hit(...)
                if ps.take_profit:
                    hit = (ps.is_buy and price >= ps.take_profit) or (not ps.is_buy and price <= ps.take_profit)
                    # NOTIF OFF: if hit: notifier.notify_tp_hit(...)
            
            sr = _compute_real_sr(candles.get("H1", []), price)
            ctx = MarketContext(symbol=sym, timestamp=datetime.now(timezone.utc))
            spread_buf_val = sl_buffer(ctx)
            ctx.metadata.update({
                "candles": candles, "current_price": price,
                "atr": context_engine._calc_atr(candles.get("H1", [])),
                "h1_support": sr["h1_support"], "h1_resistance": sr["h1_resistance"],
                "h1_trend": "bearish" if candles["H1"][-1]['close'] < candles["H1"][-5]['close'] else "bullish",
                "nearest_support": sr["h1_support"], "nearest_resistance": sr["h1_resistance"],
                "spread": spread, "spread_buffer": spread_buf_val,
                "balance": balance, "equity": equity,
                "open_positions": len(raw_positions),
            })
            
            decision = orc.best_decision(ctx)

            # ── D2 SHADOW MODE ─────────────────────────────────────────────
            # MultiStrategyRuntime runs in parallel — log only, never executes.
            try:
                from core.context.scan_context import ScanContext
                from core.features.feature_models import FeatureSnapshot
                from core.regime.regime_models import RegimeSnapshot, Regime, TrendDirection
                from core.opportunity.opportunity_models import OpportunitySnapshot, BlockReason
                from core.strategy_manager.manager import StrategyManager
                from strategies.bystra.strategy import BystraStrategy
                from runtime.multi_strategy_runtime import MultiStrategyRuntime
                from runtime.adapters.tradeplan_adapter import plan_to_decision, log_shadow_diff
                import uuid as _uuid

                _sid = str(_uuid.uuid4())
                _now = datetime.now(timezone.utc)
                _features = FeatureSnapshot(symbol=sym, timestamp=_now, scan_id=_sid,
                    candles=candles,
                    atr={tf: ctx.metadata.get("atr", 0.0) for tf in candles},
                    nearest_support={"H1": sr["h1_support"]},
                    nearest_resistance={"H1": sr["h1_resistance"]},
                )
                _regime = RegimeSnapshot(regime=Regime(1), trend_direction=TrendDirection(1), confidence=0.6)
                _opp = OpportunitySnapshot(market_allowed=True, reason=BlockReason("none"),
                    priority=7, confidence=0.8, symbol=sym, timestamp=_now, scan_id=_sid)
                _scan_ctx = ScanContext(market=ctx, features=_features, regime=_regime,
                    opportunity=_opp, scan_id=_sid, timestamp=_now)

                if not hasattr(_msr_runtime, "_ready"):
                    _msr_mgr = StrategyManager()
                    _msr_mgr.load(BystraStrategy)
                    _msr_runtime._mgr = _msr_mgr
                    _msr_runtime._rt = MultiStrategyRuntime(_msr_mgr)
                    _msr_runtime._ready = True

                _plan = _msr_runtime._rt.scan(_scan_ctx)
                _new_decision = plan_to_decision(_plan)
                log_shadow_diff(sym, decision, _new_decision)
            except Exception as _e:
                log.debug("[SHADOW ERR] %s: %s", sym, _e)
            # ── END SHADOW MODE ────────────────────────────────────────────
            if decision.action != "WAIT":
                log.info(f"Setup detected: {decision.setup_name} {decision.action} conf={decision.confidence:.0%}")
                risk_ctx = {
                    "symbol": sym, "entry": (decision.metadata.get("entry_zone") or {}).get("high"),
                    "sl": decision.metadata.get("sl"), "tp": decision.metadata.get("take_profit"),
                    "direction": decision.action, "confidence": decision.confidence,
                    "spread": spread, "balance": balance, "equity": equity,
                    "open_positions": len(raw_positions), "lot": 0.01, "sl_pips": 0, "time": time.time(),
                }
                if risk_ctx["sl"] and risk_ctx["entry"]:
                    risk_ctx["sl_pips"] = abs(risk_ctx["entry"] - risk_ctx["sl"]) * 10
                if sym in ("BTCUSD", "ETHUSD"):
                    risk_ctx["sl_pips"] = 0
                
                risk_results = {}
                for rule_name in risk_gate.list_enabled():
                    plugin = risk_gate.get(rule_name)
                    if plugin: risk_results[rule_name] = plugin.evaluate(risk_ctx, {}, decision)
                
                if all(r.status == "APPROVE" for r in risk_results.values()):
                    dedup_key = (sym, decision.setup_name, decision.action)
                    now = time.time()
                    last_seen = _seen_setups.get(dedup_key, 0.0)
                    if now - last_seen < DEDUP_WINDOW:
                        log.info(f"Dedup: skip {decision.setup_name} {decision.action} {sym} (seen {(now-last_seen):.0f}s ago)")
                    else:
                        _seen_setups[dedup_key] = now
                        log.info(f"Risk Gate: ✅ PASS — {sym}")
                        push_decision(decision)
                        monitor.add_setup(decision)
                else:
                    reasons = "; ".join(f"{n}={r.status}:{r.reason}" for n, r in risk_results.items() if r.status != "APPROVE")
                    log.info(f"Risk Gate: ❌ BLOCKED {sym}. {reasons}")
                    # NOTIF OFF: notifier.notify_risk_gate_blocked(...)
            else:
                log.info(f"No setup for {sym} (WAIT)")
            
            # Position monitoring - pass M5 candles for early exit detection
            market_update = {
                sym: {
                    "price": price,
                    "atr": ctx.metadata.get("atr", 0.0),
                    "candles": candles  # full dict with M5, M15, M30, H1
                }
            }
            # Build contracts dict from active positions
            contracts = {}
            for ps in pos_states:
                if ps.symbol == sym:
                    # Create minimal contract with execution params
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
            
            # Build pair_data for dashboard
            pair_data = {
                "price": price,
                "support": sr["h1_support"],
                "resistance": sr["h1_resistance"],
                "trend": ctx.metadata.get("h1_trend", "neutral"),
                "regime": "RANGING",
                "spread": spread,
                "atr": ctx.metadata.get("atr", 0.0),
                "session": ctx.metadata.get("h1_trend", "ASIA").upper(),
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
        
        except Exception as e:
            log.error(f"Error scanning {sym}: {e}")
    
    # Write aggregated JSON AFTER all symbols scanned
    try:
        account_data = broker.get_account_info()
        balance = account_data.balance
        equity = account_data.equity
        pos_states = broker.get_positions()
        
        status_data = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "balance": balance,
            "equity": equity,
            "floating_pnl": sum(getattr(p, 'profit_pts', 0) * getattr(p, 'volume', 0) for p in pos_states),
            "margin_percent": 0.0,
            "pairs": all_pairs_data,
            "positions": [{"side": getattr(p, 'direction', ''), "volume": getattr(p, 'volume', 0), "entry": getattr(p, 'entry_price', 0), "sl": getattr(p, 'stop_loss', 0), "tp": getattr(p, 'take_profit', 0), "pnl": getattr(p, 'profit_pts', 0) * getattr(p, 'volume', 0), "symbol": getattr(p, 'symbol', '')} for p in pos_states],
            "total_setups": sum(1 for p in all_pairs_data.values() if p.get("setup")),
        }
        
        import os, json
        os.makedirs(os.path.dirname(status_path), exist_ok=True)
        with open(status_path, "w") as f:
            json.dump(status_data, f)
    except Exception as e:
        log.error(f"Dashboard write failed: {e}")
    
    time.sleep(10)
