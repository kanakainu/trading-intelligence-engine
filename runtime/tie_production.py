#!/usr/bin/env python3
"""TIE Production Runtime — Multi-Symbol Support (XAUUSD, BTCUSD, GBPUSD)."""
import sys, time, logging, os
from datetime import datetime, timezone

# === SINGLETON LOCK ===
PID_FILE = "/tmp/tie_production.pid"
def acquire_singleton():
    """Prevent duplicate instances."""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, 0)  # Check if process exists
            print(f"ERROR: tie_production.py already running (PID {old_pid})")
            sys.exit(1)
        except (ValueError, ProcessLookupError):
            pass  # Stale PID file, continue
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

acquire_singleton()
# === END SINGLETON ===

sys.path.insert(0, '/home/ubuntu/.hermes/trading')
sys.path.insert(0, '/home/ubuntu/trading-intelligence-engine')

from gateway_client import MT5GatewayClient
from runtime.gate_observatory import GateObservatory, create_trace
from runtime.trading_intelligence import DailyProfitGovernorV2, TradeBudgetManager, OpportunityLifecycle
from runtime.adaptive_learning import PostMortemAnalyzer, AdaptiveThresholdManager
from runtime.execution_analytics import ExecutionTracker
from runtime.health_monitor import HealthMonitor
from runtime.auto_optimizer import ThresholdOptimizer
from runtime.portfolio_intelligence import PortfolioCoordinator
from core.context.context_model import MarketContext
from core.context.scan_context import ScanContext
from core.features.feature_models import FeatureSnapshot
from core.regime.regime_models import RegimeSnapshot, Regime, TrendDirection
from core.opportunity.opportunity_models import OpportunitySnapshot, BlockReason
from core.strategy_manager.manager import StrategyManager
from core.strategy.exit_orchestrator import ExitOrchestrator, ExitProfile
from strategies.bystra.strategy import BystraStrategy
from strategies.aggressive.strategy import AggressiveStrategy
from strategies.semi_hft.strategy import SemiHFTStrategyV4 as SemiHFTStrategy
from strategies.aggressive.regime.regime_engine import AggressiveRegimeEngine
from runtime.multi_strategy_runtime import MultiStrategyRuntime
from runtime.adapters.tradeplan_adapter import plan_to_decision, aggressive_regime_to_core_regime
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
import uuid

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

mgr = StrategyManager()
orch = ExitOrchestrator(min_gate_rr=1.5)
mgr.load(BystraStrategy)
mgr.load(AggressiveStrategy)
mgr.load(SemiHFTStrategy)

rt = MultiStrategyRuntime(mgr)
monitor = EntryMonitor(broker=broker, gateway=client)
pos_monitor = PositionMonitor(broker=broker)
risk_gate = build_risk_registry()
context_engine = ContextEngine()
observatory = GateObservatory()
governor = DailyProfitGovernorV2(daily_target=30.0, daily_loss_limit=50.0)
budget_mgr = TradeBudgetManager()
opp_lifecycle = OpportunityLifecycle()
adaptive_mgr = AdaptiveThresholdManager()
pma = PostMortemAnalyzer(lookback_days=30)
exec_tracker = ExecutionTracker()
health_monitor = HealthMonitor(gateway_url=URL)
optimizer = ThresholdOptimizer(lookback_days=30)
portfolio_coord = PortfolioCoordinator(max_exposure=500.0)

log.info(f"TIE Production Multi-Symbol started: {SYMBOLS}. Risk Gate active. Observatory enabled. Governor enabled.")

def _compute_real_sr(candles_h1: list, price: float = 0.0) -> dict:
    if not candles_h1:
        return {"h1_support": price, "h1_resistance": price}
    support = find_nearest_support(candles_h1, price) if price else None
    resistance = find_nearest_resistance(candles_h1, price) if price else None
    if not support or not resistance:
        pivots = find_swing_pivots(candles_h1, n=2)
        highs = [p["price"] for p in pivots if p["type"] == "high"]
        lows  = [p["price"] for p in pivots if p["type"] == "low"]
        if not support:    support    = max(lows)  if lows  else None
        if not resistance: resistance = min(highs) if highs else None
    return {"h1_support": support, "h1_resistance": resistance}

def _get_spread(client, symbol: str) -> float:
    try:
        price_data = client.price(symbol)
        return float(price_data.get("spread", 0))
    except Exception: return 10.0

HALT_FLAG = "/tmp/tie_halt"  # touch /tmp/tie_halt to stop all trading; rm to resume

# Market session hours UTC — Vibe triggers.py pattern
# ponytail: add Asian/London/NY session awareness when SessionProfile lands
_CFD_24_5 = {"XAUUSD", "GBPJPY"}  # closed Fri 21:00–Sun 22:00 UTC
_CRYPTO_247 = {"BTCUSD"}

def _market_open(sym: str, now_utc: datetime) -> bool:
    """Return False if CFD market is closed (weekend gap)."""
    if sym.upper() in _CRYPTO_247:
        return True
    # Fri 21:00 UTC → Sun 22:00 UTC = closed
    wd = now_utc.weekday()  # Mon=0 … Fri=4, Sat=5, Sun=6
    h  = now_utc.hour
    if wd == 4 and h >= 21: return False   # Friday after close
    if wd == 5: return False               # All Saturday
    if wd == 6 and h < 22: return False    # Sunday before open
    return True


while True:
    # Kill Switch — sentinel file pattern (Vibe halt.py)
    if os.path.exists(HALT_FLAG):
        log.warning("HALT FLAG active — skipping scan. rm /tmp/tie_halt to resume.")
        time.sleep(10)
        continue

    # Drawdown Guard — block all new signals if DD ≥ 35% from peak equity
    try:
        _acct = client.account() or {}
        _equity = float(_acct.get("equity", 0))
        _balance = float(_acct.get("balance", _equity))
        _peak = max(_equity, _balance)
        if _peak > 0:
            _dd_pct = (_peak - _equity) / _peak * 100
            if _dd_pct >= 35.0:
                log.warning("DD GUARD: equity=%.2f peak=%.2f DD=%.1f%% ≥ 35%% — all scans blocked.", _equity, _peak, _dd_pct)
                time.sleep(30)
                continue
    except Exception as _e:
        log.warning("DD Guard check failed: %s", _e)


    all_pairs_data = {}  # Accumulate ALL pairs per loop
    status_path = "/home/ubuntu/tie-dashboard/data/tie_status.json"

    for sym in SYMBOLS:
        try:
            now_utc = datetime.now(timezone.utc)
            if not _market_open(sym, now_utc):
                log.info("Market closed for %s (%s) — skip scan", sym, now_utc.strftime("%a %H:%M UTC"))
                continue
            log.info(f"--- Scanning {sym} ---")
            candles = {}
            for tf in ["M5", "M15", "M30", "H1"]:
                count = 40 if tf == "M5" else 20
                candles[tf] = client.candles(sym, tf, count)
            
            price_data = client.price(sym)
            if not isinstance(price_data, dict):
                log.error(f"Price data for {sym} is not a dict: {price_data}")
                continue
            price = float(price_data.get('ask', 0.0)) # Ensure it's a float, default 0.0
            spread = _get_spread(client, sym)

            if price == 0.0: # If we still have no valid price, skip this scan
                log.warning(f"Skipping {sym} scan: no valid price data from gateway. Price data: {price_data}")
                continue

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
                volume=p.get("volume", 0),
                comment=p.get("comment", ""),
                # Extended fields for TrailingManager
                strategy_id="unknown",  # Will be extracted from comment below
                unrealized_profit=p.get("profit", 0.0),  # USD PnL from broker
                rr=0.0,  # Calculate below if SL/TP available
                sl_dist_pts=0.0,  # Calculate below
                point_value=0.1,  # Default XAUUSD 0.01 lot = $0.1/point
                digits=2  # XAUUSD default
            ) for p in raw_positions]
            
            for ps in pos_states:
                if ps.symbol != sym: continue
                
                # Extract strategy_id from comment (e.g., "TIE_B_SELL" -> "bystra")
                if ps.comment and ps.comment.startswith("TIE_"):
                    parts = ps.comment.split("_")
                    if len(parts) >= 2:
                        strategy_code = parts[1]  # B, BA, BAS, A, S
                        strategy_map = {
                            "B": "bystra",
                            "BA": "bystra_aggressive",
                            "BAS": "bystra_aggressive_semi_hft",
                            "A": "aggressive",
                            "S": "semi_hft"
                        }
                        ps.strategy_id = strategy_map.get(strategy_code, "unknown")
                
                # Calculate rr, sl_dist_pts if SL/TP available
                if ps.stop_loss and ps.take_profit and ps.entry_price:
                    sl_dist = abs(ps.entry_price - ps.stop_loss)
                    tp_dist = abs(ps.take_profit - ps.entry_price)
                    ps.sl_dist_pts = sl_dist
                    ps.rr = tp_dist / sl_dist if sl_dist > 0 else 0.0
                
                profit = ps.profit_pts * ps.volume * 100
                if ps.stop_loss:
                    hit = (ps.is_buy and price <= ps.stop_loss) or (not ps.is_buy and price >= ps.stop_loss)
                    # NOTIF OFF: if hit: notifier.notify_sl_hit(...)
                if ps.take_profit:
                    hit = (ps.is_buy and price >= ps.take_profit) or (not ps.is_buy and price <= ps.take_profit)
                    # NOTIF OFF: if hit: notifier.notify_tp_hit(...)
            
            sr = _compute_real_sr(candles.get("H1", []), price)
            log.debug(f"GBPJPY H1 candles after _compute_real_sr: {candles.get('H1', [])}")
            ctx = MarketContext(symbol=sym, timestamp=datetime.now(timezone.utc))
            spread_buf_val = sl_buffer(ctx)
            ctx.metadata.update({
                "candles": candles, "current_price": price,
                "atr": context_engine._calc_atr(candles.get("H1", [])),
                "h1_support": sr["h1_support"], "h1_resistance": sr["h1_resistance"],
                "h1_trend": "bearish" if candles["H1"] and candles["H1"][-1]['close'] < candles["H1"][-5]['close'] else "bullish",
                "nearest_support": sr["h1_support"], "nearest_resistance": sr["h1_resistance"],
                "spread": spread, "spread_buffer": spread_buf_val,
                "balance": balance, "equity": equity,
                "open_positions": len(raw_positions),
            })
            
            # Build ScanContext for MultiStrategyRuntime
            _sid = str(uuid.uuid4())
            _now = datetime.now(timezone.utc)
            _features = FeatureSnapshot(symbol=sym, timestamp=_now, scan_id=_sid,
                candles=candles,
                atr={tf: ctx.metadata.get("atr", 0.0) for tf in candles},
                nearest_support={"H1": sr["h1_support"]},
                nearest_resistance={"H1": sr["h1_resistance"]},
            )
            log.debug(f"GBPJPY FeatureSnapshot candles: {candles}")
            _regime_engine = AggressiveRegimeEngine()
            agg_regime_snapshot = _regime_engine.classify(_features)
            _regime = aggressive_regime_to_core_regime(agg_regime_snapshot)

            _opp = OpportunitySnapshot(market_allowed=True, reason=BlockReason.NONE,
                priority=7, confidence=0.8, symbol=sym, timestamp=_now, scan_id=_sid)
            _scan_ctx = ScanContext(market=ctx, features=_features, regime=_regime,
                opportunity=_opp, scan_id=_sid, timestamp=_now)

            trade_plan = rt.scan(_scan_ctx)
            decision = plan_to_decision(trade_plan)

            # === DECISION TRACE V2 ===
            trace = create_trace(scan_id=_sid, symbol=sym, strategy="TIE_V3")

            if decision.action != "WAIT":
                observatory.log_gate(trace, "Detector", "PASS", current_value=decision.confidence * 100, reason=f"setup={decision.setup_name}")
                # --- ADAPTIVE EXIT ORCHESTRATOR ---
                _entry = (decision.metadata.get("entry_zone") or {}).get("high") or price
                _sl = decision.metadata.get("sl") or 0.0
                _tp = decision.metadata.get("take_profit") or 0.0

                if _sl and _tp:
                    opt = orch.optimize(
                        strategy_id=decision.setup_name,
                        symbol=sym,
                        entry=_entry,
                        sl=_sl,
                        tp=_tp,
                    )
                    decision.metadata["sl"] = opt.sl
                    decision.metadata["take_profit"] = opt.tp
                    decision.metadata["risk_reward"] = opt.rr
                    decision.metadata["trailing_type"] = opt.trailing_type
                    decision.metadata["is_adjusted"] = opt.adjusted
                    log.info("ExitOrchestrator adjusted SL/TP for %s: new SL=%.2f TP=%.2f RR=%.2f (adj=%s)",
                             decision.setup_name, opt.sl, opt.tp, opt.rr, opt.adjusted)

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

                # Build setup detail for dashboard (capture BEFORE gate decision)
                entry_zone = decision.metadata.get("entry_zone") or {}
                setup_detail = {
                    "strategy": decision.setup_name.split("_")[0] if "_" in decision.setup_name else "Unknown",
                    "setup_name": decision.setup_name,
                    "direction": decision.action,  # TradeDecision uses 'action'
                    "confidence": round(decision.confidence * 100, 1),
                    "entry": round(entry_zone.get("high") or entry_zone.get("low") or price, 5),
                    "sl": round(decision.metadata.get("sl") or 0.0, 5),
                    "tp": round(decision.metadata.get("take_profit") or 0.0, 5),
                    "danger_zone": round(decision.metadata.get("danger_zone") or 0.0, 5),
                    "risk_reward": round(decision.metadata.get("risk_reward") or 0.0, 2),
                    "trailing_type": decision.metadata.get("trailing_type", "fixed"),
                    "is_adjusted": decision.metadata.get("is_adjusted", False),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                if all(r.status == "APPROVE" for r in risk_results.values()):
                    dedup_key = (sym, decision.setup_name, decision.action)
                    now = time.time()
                    last_seen = _seen_setups.get(dedup_key, 0.0)
                    if now - last_seen < DEDUP_WINDOW:
                        log.info(f"Dedup: skip {decision.setup_name} {decision.action} {sym} (seen {(now-last_seen):.0f}s ago)")
                        setup_detail["status"] = "DEDUP"
                        setup_detail["gate_reason"] = f"Dedup: seen {(now-last_seen):.0f}s ago"
                        observatory.log_gate(trace, "Dedup", "FAIL", reason=f"seen {(now-last_seen):.0f}s ago")
                    else:
                        _seen_setups[dedup_key] = now
                        
                        # === TRADING INTELLIGENCE GATES ===
                        can_trade, gov_reason = governor.can_trade()
                        if not can_trade:
                            log.info(f"Governor STOP: {gov_reason}")
                            setup_detail["status"] = "GOVERNOR_HALT"
                            setup_detail["gate_reason"] = gov_reason
                            observatory.log_gate(trace, "Governor", "FAIL", reason=gov_reason)
                        # Extract strategy key from setup_name (B_BUY -> bystra, A_SELL -> aggressive, S_BUY -> semi_hft)
                        strat_key = decision.setup_name.split("_")[0].lower()
                        strat_map = {"b": "bystra", "a": "aggressive", "s": "semi_hft"}
                        strategy_name = strat_map.get(strat_key, strat_key)
                        if not budget_mgr.can_consume(strategy_name):
                            log.info(f"Budget exhausted for {decision.setup_name}")
                            setup_detail["status"] = "BUDGET_EXHAUSTED"
                            setup_detail["gate_reason"] = f"Trade budget consumed"
                            observatory.log_gate(trace, "TradeBudget", "FAIL", reason="budget exhausted")
                        else:
                            budget_mgr.consume(strategy_name)
                            opp_lifecycle.add(
                                strategy=decision.setup_name.split("_")[0].lower(),
                                symbol=sym,
                                direction=decision.action,
                                confidence=decision.confidence,
                                spread=spread
                            )
                            log.info(f"Risk Gate: ✅ PASS — {sym}")
                            setup_detail["status"] = "APPROVED"
                            setup_detail["gate_reason"] = "All gates passed"
                            observatory.log_gate(trace, "RiskGate", "PASS", reason="all rules approve")
                            
                            # === EXECUTE ORDER TO MT5 ===
                            from adapters.broker.models import OrderRequest
                            try:
                                req = OrderRequest(
                                    symbol=sym,
                                    side=decision.action,  # BUY/SELL
                                    volume=decision.metadata.get("lot", 0.01),
                                    stop_loss=decision.metadata.get("sl"),
                                    take_profit=decision.metadata.get("take_profit"),
                                    comment=f"TIE_{decision.setup_name}"
                                )
                                resp = broker.submit_order(req)
                                if resp.status == "FILLED":
                                    log.info(f"✅ ORDER EXECUTED: {sym} {decision.action} {req.volume} lot | SL={req.stop_loss} TP={req.take_profit} ticket={resp.order_id}")
                                    observatory.log_gate(trace, "Execution", "PASS", reason=f"order placed ticket={resp.order_id}")
                                    monitor.add_setup(decision)
                                else:
                                    log.error(f"❌ ORDER FAILED: {resp.error}")
                                    observatory.log_gate(trace, "Execution", "FAIL", reason=resp.error or "rejected")
                            except Exception as ex:
                                log.error(f"Order exception: {ex}")
                                observatory.log_gate(trace, "Execution", "FAIL", reason=str(ex))
                else:
                    reasons = "; ".join(f"{n}={r.status}:{r.reason}" for n, r in risk_results.items() if r.status != "APPROVE")
                    log.info(f"Risk Gate: ❌ BLOCKED {sym}. {reasons}")
                    setup_detail["status"] = "BLOCKED"
                    setup_detail["gate_reason"] = reasons
                    observatory.log_gate(trace, "RiskGate", "FAIL", reason=reasons)
                    # NOTIF OFF: notifier.notify_risk_gate_blocked(...)
            else:
                log.info(f"No setup for {sym} (WAIT)")
                setup_detail = None
                observatory.finalize_trace(trace, "NO_TRADE", rejection_reason="no_signal")
            
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
                    # Extract strategy code from comment (e.g., "TIE_B_SELL" -> "B")
                    strategy_code = "B"  # default
                    if ps.comment and ps.comment.startswith("TIE_"):
                        parts = ps.comment.split("_")
                        if len(parts) >= 2:
                            strategy_code = parts[1]  # B, BA, BAS, A, S
                    
                    # Strategy-specific exit config
                    exit_configs = {
                        "B":   {"be_trigger_atr": 0.5, "trail_trigger_atr": 1.0, "trail_offset_atr": 0.3, "partial_tp_pct": 0.5},      # Bystra swing
                        "BA":  {"be_trigger_atr": 0.4, "trail_trigger_atr": 0.8, "trail_offset_atr": 0.3, "partial_tp_pct": 0.4},      # Bystra+Aggressive
                        "BAS": {"be_trigger_atr": 0.3, "trail_trigger_atr": 0.6, "trail_offset_atr": 0.2, "partial_tp_pct": 0.3},      # All 3
                        "A":   {"be_trigger_atr": 0.3, "trail_trigger_atr": 0.6, "trail_offset_atr": 0.25, "partial_tp_pct": 0.4},      # Aggressive momentum
                        "S":   {"be_trigger_atr": 0.15, "trail_trigger_atr": 0.3, "trail_offset_atr": 0.15, "partial_tp_pct": 0.3},      # SemiHFT scalping
                    }
                    cfg = exit_configs.get(strategy_code, exit_configs["B"])
                    
                    # Create contract with strategy-specific execution params
                    contracts[ps.position_id] = type('Contract', (), {
                        'metadata': {
                            'be_trigger_atr': cfg["be_trigger_atr"],
                            'trail_trigger_atr': cfg["trail_trigger_atr"],
                            'trail_offset_atr': cfg["trail_offset_atr"],
                            'partial_tp_pct': cfg["partial_tp_pct"],
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
                "setup": setup_detail  # Full setup detail with status, reason, strategy, SL/TP
            }
            
            all_pairs_data[sym] = pair_data
        
        except Exception as e:
            import traceback
            log.error(f"Error scanning {sym}: {e}\n{traceback.format_exc()}")
    
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
            "floating_pnl": sum(getattr(p, 'unrealized_profit', 0) for p in pos_states),
            "margin_percent": 0.0,
            "pairs": all_pairs_data,
            "positions": [{"side": getattr(p, 'side', ''), "volume": getattr(p, 'volume', 0), "entry": getattr(p, 'entry_price', 0), "sl": getattr(p, 'stop_loss', 0), "tp": getattr(p, 'take_profit', 0), "pnl": getattr(p, 'unrealized_profit', 0), "symbol": getattr(p, 'symbol', '')} for p in pos_states],
            "total_setups": sum(1 for p in all_pairs_data.values() if p.get("setup")),
        }
        
        import os, json
        os.makedirs(os.path.dirname(status_path), exist_ok=True)
        with open(status_path, "w") as f:
            json.dump(status_data, f)
    except Exception as e:
        log.error(f"Dashboard write failed: {e}")
    
    # Update EntryMonitor for all active setups
    monitor.update()

    # === 5 INTELLIGENCE ENGINES ACTIVE ===
    # P3: Health check every 60 scans (~10 min)
    if not hasattr(monitor, '_health_counter'): monitor._health_counter = 0
    monitor._health_counter += 1
    if monitor._health_counter >= 60:
        health_status = health_monitor.get_status()
        if health_status['status'] != 'OK':
            log.warning(f"Health: {health_status}")
        monitor._health_counter = 0

    # P1: Adaptive learning — apply recommendations every 6 hours
    if not hasattr(monitor, '_adapt_counter'): monitor._adapt_counter = 0
    monitor._adapt_counter += 1
    if monitor._adapt_counter >= 2160:  # 6 hours * 360 scans
        recs = pma.recommend_adjustments()
        if recs:
            adaptive_mgr.apply_recommendations(recs)
            log.info(f"Adaptive: applied {len(recs)} adjustments")
        monitor._adapt_counter = 0

    # P4: Auto optimization — run daily
    if not hasattr(monitor, '_opt_counter'): monitor._opt_counter = 0
    monitor._opt_counter += 1
    if monitor._opt_counter >= 8640:  # 24 hours * 360 scans
        opt_results = optimizer.optimize_all()
        if opt_results:
            optimizer.apply_to_adaptive_manager(opt_results, adaptive_mgr)
            log.info(f"Optimizer: {len(opt_results)} detectors optimized")
        monitor._opt_counter = 0

    time.sleep(10)
