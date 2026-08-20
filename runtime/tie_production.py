#!/usr/bin/env python3
"""TIE Production Runtime — XAUUSD Only (user-tuned 2026-08-05)."""
import sys, time, logging, os, json
from datetime import datetime, timezone

# === SINGLETON LOCK ===
PID_FILE = "/tmp/tie_production.pid"
def acquire_singleton():
    """Prevent duplicate instances. Auto-clears stale PID on restart."""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                old_pid = int(f.read().strip())
            if old_pid == os.getpid():
                return  # Same process, skip
            os.kill(old_pid, 0)  # Check if process exists
            # Process alive — check if it's actually our script
            try:
                with open(f"/proc/{old_pid}/cmdline") as f:
                    cmdline = f.read()
                if "tie_production" not in cmdline:
                    raise ProcessLookupError  # Different process reused PID
            except (IOError, OSError):
                raise ProcessLookupError  # Can't read cmdline — assume stale
            sys.exit(0)  # Exit cleanly — duplicate prevention, no output needed
        except (ValueError, ProcessLookupError, OSError):
            os.remove(PID_FILE)  # Stale PID — clean up
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()) + "\n")

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
from core.features import compute_features, FeatureInputs
from core.regime.regime_models import RegimeSnapshot, Regime, TrendDirection
from core.opportunity.opportunity_models import OpportunitySnapshot, BlockReason
from core.strategy_manager.manager import StrategyManager
from core.strategy.exit_orchestrator import ExitOrchestrator, ExitProfile
from strategies.riri_scalps.strategy import RiriScalpsStrategy
from strategies.three_ca.strategy import ThreeCaStrategy
from strategies.aggressive.regime.regime_engine import AggressiveRegimeEngine
from runtime.multi_strategy_runtime import MultiStrategyRuntime
from runtime.adapters.tradeplan_adapter import plan_to_decision, aggressive_regime_to_core_regime
# DISABLED: entry_monitor submits Riri_ orders — duplicate engine, replaced by TIE_ path
# from runtime.entry_monitor import EntryMonitor
from runtime.position_monitor import PositionMonitor
from runtime.position_state import PositionState
from adapters.broker.mt5_broker import MT5BrokerAdapter
from runtime.hck_wire import push_decision
from shared.news_sentinel import check_news_blackout
from shared.regime_detector import RegimeDetector, MarketRegime
from shared.regime_allocator import RegimeAllocator
from core.rules.risk.risk_registry import build_risk_registry
from core.rules.plugins.plugin_interface import RuleResult
from detectors.common import find_swing_pivots, find_nearest_support, find_nearest_resistance, sl_buffer
from core.context.context_engine import ContextEngine
from reasoning.llm_reasoner import LLMReasoner
import uuid

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(message)s')
log = logging.getLogger("TIE_Production")

# Also write to file so dashboard can read fresh logs
_fh = logging.FileHandler("/home/ubuntu/trading-intelligence-engine/logs/tie_production.log", mode="a")
_fh.setFormatter(logging.Formatter('%(asctime)s %(name)s %(message)s'))
logging.getLogger().addHandler(_fh)

URL = 'https://chips-extension-extensions-wearing.trycloudflare.com'
TOKEN = 'Jojo_56790@_000tUi_OO9'
SYMBOLS = ['XAUUSD']  # user-tuned 2026-08-05: XAUUSD only, save bandwidth

_seen_setups = {}  # {(sym, setup_name, direction): timestamp} — dedup 1 min
DEDUP_WINDOW = 60  # seconds — 2026-08-06: back to 60 per user request

client = MT5GatewayClient(URL, TOKEN)
broker = MT5BrokerAdapter(base_url=URL, token=TOKEN)
broker.initialize()

mgr = StrategyManager()
orch = ExitOrchestrator(min_gate_rr=1.5)
# Bystra disabled — mati suri, replaced by ThreeCa standalone
mgr.load(ThreeCaStrategy)
mgr.load(RiriScalpsStrategy)

# Global Regime Detector (Nexus A12 style)
regime_detector = RegimeDetector()
regime_allocator = RegimeAllocator(regime_detector)

rt = MultiStrategyRuntime(mgr)
# DISABLED: EntryMonitor submits Riri_ orders — duplicate engine, replaced by TIE_ path
# monitor = EntryMonitor(broker=broker, gateway=client)
# Wire PositionMonitor to broker via callback
def handle_pos_result(pos, result):
    """Wire PositionMonitor result to broker modify/close."""
    if result.action == "modify" and (result.new_sl or result.new_tp):
        # Gateway /trade/modify REQUIRES both sl AND tp — use pos.take_profit if new_tp is None
        _sl = result.new_sl or pos.stop_loss
        _tp = result.new_tp or pos.take_profit
        if not _sl or not _tp:
            log.warning(f"Modify {pos.position_id} skipped: SL={_sl} TP={_tp} — missing value")
            return
        resp = broker.modify_order(str(pos.position_id), stop_loss=_sl, take_profit=_tp)
        log.info(f"Modify {pos.position_id}: SL={_sl} TP={_tp} -> {getattr(resp, 'status', '?')}")
    elif result.action == "close":
        resp = broker.close_position(str(pos.position_id))
        log.info(f"Close {pos.position_id}: {result.reason} -> {getattr(resp, 'status', '?')}")

pos_monitor = PositionMonitor(on_result=handle_pos_result, broker=broker)
risk_gate = build_risk_registry()
context_engine = ContextEngine()
observatory = GateObservatory()
governor = DailyProfitGovernorV2(daily_target=30.0, daily_loss_limit=200.0)
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
        return float(price_data.get("spread", 0)) / 1000.0
    except Exception: return 10.0

HALT_FLAG = "/tmp/tie_halt"  # touch /tmp/tie_halt to stop all trading; rm to resume

# Market session hours UTC — Vibe triggers.py pattern
# ponytail: add Asian/London/NY session awareness when SessionProfile lands
_CFD_24_5 = {"XAUUSD"}  # closed Fri 21:00–Sun 22:00 UTC
_CRYPTO_247 = set()  # crypto removed — XAUUSD only

def write_dashboard_status(all_pairs_data, broker, status_path):
    """Update dashboard JSON for frontend consumption."""
    try:
        from datetime import datetime, timezone
        import os, json
        account_data = broker.get_account_info()
        balance = account_data.balance
        equity = account_data.equity
        pos_states = broker.get_positions()
        
        # Calculate daily PnL relative to day start
        daily_pnl = 0.0
        try:
            ds_file = "/home/ubuntu/trading-intelligence-engine/data/tie_day_start.json"
            if os.path.exists(ds_file):
                with open(ds_file) as f:
                    day_start = float(json.load(f).get("balance", 0))
                if day_start > 0:
                    daily_pnl = equity - day_start
        except: pass
        
        # Get daily target from governor
        daily_target = 30.0  # fallback
        try:
            from runtime.trading_intelligence import DailyProfitGovernorV2
            # Reuse the governor instance if accessible, or recreate
            daily_target = 30.0  # Hardcoded fallback matching governor config
        except: pass
        
        status_data = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "balance": balance,
            "equity": equity,
            "daily_pnl": round(daily_pnl, 2),
            "daily_target": daily_target,  # NEW: Add daily target
            "floating_pnl": sum(getattr(p, 'unrealized_profit', 0) for p in pos_states),
            "margin_percent": 0.0,
            "pairs": all_pairs_data,
            "positions": [{"side": getattr(p, 'side', ''), "volume": getattr(p, 'volume', 0), "entry": getattr(p, 'entry_price', 0), "sl": getattr(p, 'stop_loss', 0), "tp": getattr(p, 'take_profit', 0), "pnl": getattr(p, 'unrealized_profit', 0), "symbol": getattr(p, 'symbol', '')} for p in pos_states],
            "total_setups": sum(1 for p in all_pairs_data.values() if p.get("setup")),
        }
        
        os.makedirs(os.path.dirname(status_path), exist_ok=True)
        with open(status_path, "w") as f:
            json.dump(status_data, f)
    except Exception as e:
        import logging
        logging.getLogger("TIE_Production").error(f"Dashboard write failed: {e}")


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

# Heartbeat for manual_trailing_v2.py watchdog
HEARTBEAT_PATH = "/tmp/tie_production_heartbeat.txt"
def write_heartbeat():
    try:
        with open(HEARTBEAT_PATH, "w") as f:
            f.write(str(time.time()))
    except Exception:
        pass

while True:
    write_heartbeat()  # Write heartbeat every loop iteration
    # Kill Switch — sentinel file pattern (Vibe halt.py)
    if os.path.exists(HALT_FLAG):
        log.warning("HALT FLAG active — skipping scan. rm /tmp/tie_halt to resume.")
        time.sleep(10)
        continue

    # News Sentinel auto-refresh every 15 minutes
    _blackout_file = "/tmp/tie_news_blackout.json"
    _now_ts = time.time()
    _blackout_age = _now_ts - os.path.getmtime(_blackout_file) if os.path.exists(_blackout_file) else 9999
    if _blackout_age > 900:  # 15 min stale → refresh
        try:
            import asyncio as _aio
            from shared.news_sentinel import NewsSentinel as _NS
            _aio.get_event_loop().run_until_complete(_NS().check_blackout())
            log.debug("News sentinel refreshed")
        except Exception as _ne:
            log.warning("News sentinel refresh failed: %s", _ne)

    # Daily Target Hibernate — MUST run before DD Guard to skip client.account() API call
    try:
        _ds_file = "/tmp/tie_day_start.json"
        _ds_persist = "/home/ubuntu/trading-intelligence-engine/data/tie_day_start.json"
        _hibernate_s = int(os.environ.get("TIE_HIBERNATE_INTERVAL_S", "1200"))  # 20min default
        if not os.path.exists(_ds_file) and os.path.exists(_ds_persist):
            # Restore from persistent store after VPS reboot
            import shutil; shutil.copy2(_ds_persist, _ds_file)
        if os.path.exists(_ds_file):
            with open(_ds_file) as _f:
                _day_start_val = float(json.load(_f).get("balance", 0))
            if _day_start_val > 0:
                _status_path = "/home/ubuntu/tie-dashboard/data/tie_status.json"
                _last_equity = 0.0
                if os.path.exists(_status_path):
                    try:
                        with open(_status_path) as _sf:
                            _last_equity = float(json.load(_sf).get("equity", 0))
                    except Exception:
                        pass
                if _last_equity > 0:
                    _daily_pnl = _last_equity - _day_start_val
                    if _daily_pnl >= 30.0:  # MUST MATCH daily_target in governor (30.0)
                        _now_utc = datetime.now(timezone.utc)
                        _day_start_mtime = datetime.fromtimestamp(os.path.getmtime(_ds_file), tz=timezone.utc)
                        if _now_utc.date() > _day_start_mtime.date():
                            # NEW UTC DAY: reset day_start to current equity
                            _reset_payload = json.dumps({"balance": _last_equity})
                            with open(_ds_file, "w") as _f:
                                _f.write(_reset_payload)
                            with open(_ds_persist, "w") as _f:
                                _f.write(_reset_payload)
                            log.info("DAY RESET: new UTC day, day_start=%.2f", _last_equity)
                        else:
                            if _daily_pnl >= 100.0: # Daily Target $100
                                write_dashboard_status(all_pairs_data if 'all_pairs_data' in locals() else {}, broker, "/home/ubuntu/tie-dashboard/data/tie_status.json")
                                log.info("HIBERNATE: daily target hit (PnL=$%.2f >= $100). Sleep %ds. Zero API calls.", _daily_pnl, _hibernate_s)
                                time.sleep(_hibernate_s)
                                continue
    except Exception as _e:
        log.warning("Hibernate check failed: %s", _e)

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
            for tf in ["M1", "M5", "M15", "M30", "H1"]:
                count = 100 if tf == "M1" else 40 if tf == "M5" else 20
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

            # Daily PnL tracker — day-start balance persisted across restarts
            _dp_file = "/tmp/tie_day_start.json"
            _dp_persist = "/home/ubuntu/trading-intelligence-engine/data/tie_day_start.json"
            try:
                if os.path.exists(_dp_file):
                    with open(_dp_file) as _f:
                        _day_start = float(json.load(_f).get("balance", balance))
                elif os.path.exists(_dp_persist):
                    # Restore from persistent store after VPS reboot
                    with open(_dp_persist) as _f:
                        _day_start = float(json.load(_f).get("balance", balance))
                    with open(_dp_file, "w") as _f:
                        json.dump({"balance": _day_start}, _f)
                else:
                    _day_start = balance
                    _payload = json.dumps({"balance": _day_start})
                    with open(_dp_file, "w") as _f:
                        _f.write(_payload)
                    with open(_dp_persist, "w") as _f:
                        _f.write(_payload)
            except Exception:
                _day_start = balance
            daily_pnl = equity - _day_start

            # SL/TP Hit Notification
            from runtime.telegram_notifier import TelegramNotifier
            notifier = TelegramNotifier(TOKEN)
            
            pos_states = [PositionState(
                position_id=str(p.get("ticket")),
                symbol=p.get("symbol"),
                direction=p.get("direction", p.get("type", "")).upper(),
                entry_price=float(p.get("open_price") or p.get("price_open") or 0),
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
                # Extract strategy_id from comment — always, regardless of symbol
                if ps.comment and ps.comment.startswith("TIE_"):
                    parts = ps.comment.split("_")
                    if len(parts) >= 2:
                        strategy_code = parts[1]  # B, BA, BAS, A, S
                        strategy_map = {
                            "B": "bystra",
                            "BA": "bystra",
                            "BAS": "bystra",
                            "A": "riri_scalps",
                            "S": "riri_scalps"
                        }
                        ps.strategy_id = strategy_map.get(strategy_code, "riri_scalps")
                else:
                    ps.strategy_id = "riri_scalps"  # Default fallback for TIE orders

                if ps.symbol != sym: continue

                
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
            log.debug(f"H1 candles after _compute_real_sr: {candles.get('H1', [])}")

            # === CONTEXT ENGINE CENTRAL ===
            # This builds the complete MarketContext including Z-Score, ATR, etc.
            market_data_for_context = {
                "symbol": sym,
                "timestamp": now_utc,
                "price": price, # Pass current live price
                "spread": spread,
                "market_open": _market_open(sym, now_utc),
                "candles": candles.get("M5", [])  # FIXED: ContextEngine needs M5 candles for proper ATR/Z-Score
            }
            ctx = context_engine.build(market_data_for_context)
            log.debug(f"MarketContext built: price={ctx.price:.2f} z_score={ctx.vwap_z_score:.2f} atr={ctx.atr:.2f}")

            # Build ScanContext for MultiStrategyRuntime
            _sid = str(uuid.uuid4())
            _now = datetime.now(timezone.utc)

            # Feature Engine Central — full indicator computation (EMA, ATR, VWAP, momentum, volume)
            _feat_inputs = FeatureInputs(
                candles=candles,
                spread=spread,
                symbol=sym,
                timestamp=_now,
                scan_id=_sid,
                current_tick={"bid": price, "ask": price + spread},
                balance=balance, # Inject account data
                equity=equity,
                open_positions=len(raw_positions),
                raw_positions=raw_positions,
                current_price=price # Pass current live price to features
            )
            _features = compute_features(_feat_inputs)

            # 🧠 NEXUS A12: Regime Detection + Automatic Allocation (Transmission)
            _regime_snap = regime_allocator.allocate(_features, time.time())
            log.info(f"MARKET REGIME: {_regime_snap.regime.value} (strength={_regime_snap.strength:.0f}) | SUGGESTED ENGINE: {_regime_snap.suggested_engine}")
            if _regime_snap.regime in (MarketRegime.CHOPPY, MarketRegime.CHAOS):
                log.warning(f"REGIME GATE: {_regime_snap.regime.value} — MR disabled, structural only")
                # Don't skip — RiriScalps Engine B/C still valid in choppy/chaos

            # Inject S/R via dataclasses.replace (frozen-safe)
            import dataclasses
            _features = dataclasses.replace(
                _features,
                nearest_support={"H1": sr["h1_support"]},
                nearest_resistance={"H1": sr["h1_resistance"]},
            )
            log.debug(f"FeatureSnapshot candles: {candles}")
            _regime_engine = AggressiveRegimeEngine()
            agg_regime_snapshot = _regime_engine.classify(_features)
            _regime = aggressive_regime_to_core_regime(agg_regime_snapshot)
            # Carry regime_snap.strength via confidence so pullback_filter trending_override fires
            from dataclasses import replace as _dc_replace
            _regime = _dc_replace(_regime, confidence=min(_regime_snap.strength / 100.0, 1.0))

            _opp = OpportunitySnapshot(market_allowed=True, reason=BlockReason.NONE,
                priority=7, confidence=0.8, symbol=sym, timestamp=_now, scan_id=_sid)
            _scan_ctx = ScanContext(market=ctx, features=_features, regime=_regime,
                opportunity=_opp, scan_id=_sid, timestamp=_now)

            trade_plan = rt.scan(_scan_ctx)
            decision = plan_to_decision(trade_plan)

            # === DECISION TRACE V2 ===
            trace = create_trace(scan_id=_sid, symbol=sym, strategy="TIE_V4")


            if decision.action != "WAIT":
                # === VOLATILITY POSITION SIZING (GS Quant inspired) ===
                from shared.volatility_sizing import calc_lot
                atr_val = _features.atr.get("M5", 0) if hasattr(_features, "atr") else 0
                
                # Get strategy name for portfolio optimizer
                _strat_key = decision.setup_name.split("_")[0].lower()
                _strat_map = {"b": "bystra", "t": "three_ca", "r": "riri_scalps", "a": "riri_scalps", "s": "riri_scalps", "as": "riri_scalps"}
                _strat_name = _strat_map.get(_strat_key, "riri_scalps")
                
                decision.metadata["volume"] = calc_lot(equity, atr_val, strategy_id=_strat_name)
                
                # === MEAN-REVERSION + WICK SPIKE (Boskuh Logic) ===
                from shared.mean_reversion_filter import check as _mean_rev_check
                mr_verdict = _mean_rev_check(_features, _features.candles, decision.action)
                if not mr_verdict.allowed:
                    observatory.log_gate(trace, "MeanRev", "FAIL", current_value=mr_verdict.z_score, reason=mr_verdict.reason)
                    continue
                if mr_verdict.is_spike:
                    log.info(f"🚀 [SPIKE_CONFIRM] {decision.action} confirmed by Wick Rejection!")
                
                observatory.log_gate(trace, "Detector", "PASS", current_value=decision.confidence * 100, reason=f"setup={decision.setup_name} lot={decision.metadata['volume']}")
                # --- ADAPTIVE EXIT ORCHESTRATOR ---
                # FIX: entry_zone["high"] for BUY, entry_zone["low"] for SELL
                entry_zone = decision.metadata.get("entry_zone") or {}
                # FIX #54: Use LIVE price as entry anchor (not stale candle entry_zone)
                # Stale entry → SL/TP mismatch → Risk Gate false rejects
                _live_price = price if isinstance(price, (int, float)) and price > 0 else 0.0
                _entry = _live_price or (entry_zone.get("high") if decision.action == "BUY" else entry_zone.get("low")) or 0.0
                _sl = decision.metadata.get("sl") or 0.0
                _tp = decision.metadata.get("take_profit") or 0.0
                
                if _sl and _tp:
                    # FIX #54b: normalize SL/TP side vs LIVE entry using dynamic ATR buffer
                    _atr = _features.get_atr("M5") or 2.0
                    _buffer = max(_atr * 1.5, 3.0)  # Dynamic buffer based on volatility
                    
                    if decision.action == "SELL":
                        if _sl <= _entry:
                            _sl = _entry + _buffer
                        if _tp >= _entry:
                            _tp = _entry - (_buffer * 1.5) # Default 1:1.5 RR for fallback
                    elif decision.action == "BUY":
                        if _sl >= _entry:
                            _sl = _entry - _buffer
                        if _tp <= _entry:
                            _tp = _entry + (_buffer * 1.5)
                    # ExitOrchestrator disabled — manual_trailing_v2 handle all SL/TP modify
                    # opt = orch.optimize(
                    #     strategy_id=decision.setup_name,
                    #     symbol=sym,
                    #     entry=_entry,
                    #     sl=_sl,
                    #     tp=_tp,
                    #     direction=decision.action,
                    # )
                    # decision.metadata["sl"] = opt.sl
                    # decision.metadata["take_profit"] = opt.tp
                    # decision.metadata["risk_reward"] = opt.rr
                    # decision.metadata["trailing_type"] = opt.trailing_type
                    # decision.metadata["is_adjusted"] = opt.adjusted
                    # log.info("ExitOrchestrator adjusted SL/TP for %s: new SL=%.2f TP=%.2f RR=%.2f (adj=%s)",
                    #          decision.setup_name, opt.sl, opt.tp, opt.rr, opt.adjusted)
                    decision.metadata["sl"] = _sl
                    decision.metadata["take_profit"] = _tp
                    decision.metadata["risk_reward"] = round(abs(_tp - _entry) / abs(_entry - _sl), 2) if abs(_entry - _sl) > 0 else 0.0

                log.info(f"Setup detected: {decision.setup_name} {decision.action} conf={decision.confidence:.0%}")
                
                # FIX: entry_zone["high"] for BUY, entry_zone["low"] for SELL
                entry_zone = decision.metadata.get("entry_zone") or {}
                risk_entry = entry_zone.get("high") if decision.action == "BUY" else entry_zone.get("low")
                
                risk_ctx = {
                    "symbol": sym, "entry": risk_entry,
                    "sl": decision.metadata.get("sl"), "tp": decision.metadata.get("take_profit"),
                    "direction": decision.action, "confidence": decision.confidence,
                    "spread": spread, "balance": balance, "equity": equity,
                    "daily_pnl": daily_pnl,  # equity - day_start_balance (realized + floating)
                    "open_positions": len(raw_positions), "lot": decision.metadata.get("volume", 0.01), "sl_pips": 0, "time": time.time(),
                }
                if risk_ctx["sl"] and risk_ctx["entry"]:
                    risk_ctx["sl_pips"] = abs(risk_ctx["entry"] - risk_ctx["sl"]) * 10
                # XAUUSD only — no crypto pip override needed

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

                # === ⚔️ NEXUS CROSS-STRATEGY DEBATE (Global Direction Lock) ===
                if decision.action != "WAIT":
                    # Check for existing positions in the OPPOSITE direction
                    _opp_positions = [p for p in raw_positions 
                                     if p.get("direction", p.get("type", "")).upper() != decision.action.upper()
                                     and p.get("symbol", "") == sym]
                    _opp_pos_count = len(_opp_positions)
                    
                    if _opp_pos_count > 0:
                        # Exception: Bystra can trade reversal if confidence is very high (>85%)
                        _is_bystra = "B_" in decision.setup_name

                        # === CONTRA-HEDGE REDUCED SIZE ===
                        # Opposing positions exist → allow entry but scale down lot size
                        # Lot = max(0.01, normal_lot / (opp_count + 1)) — min fallback 0.01
                        if not _is_bystra and decision.confidence >= 0.65:
                            _normal_lot = decision.metadata.get("volume", 0.01)
                            _reduced_lot = max(0.01, round(_normal_lot / (_opp_pos_count + 1), 2))
                            decision.metadata["volume"] = _reduced_lot
                            log.info(f"⚖️ CONTRA-HEDGE: {decision.action} conf={decision.confidence:.2f} lot {_normal_lot}→{_reduced_lot} ({_opp_pos_count} opposing)")
                            # Fall through to entry with reduced lot

                        elif not (_is_bystra and decision.confidence > 0.85):
                            log.warning(f"⚔️ CROSS-DEBATE BLOCK: {decision.setup_name} {decision.action} rejected! {_opp_pos_count} opposing positions open.")
                            setup_detail["status"] = "DEBATE_CONFLICT"
                            setup_detail["gate_reason"] = f"Conflict: {_opp_pos_count} opposing positions open"
                            observatory.log_gate(trace, "Debate", "FAIL", reason="hedge_conflict")
                            continue

                if all(r.status == "APPROVE" for r in risk_results.values()):
                    # Adaptive max positions per strategy: TRENDING=5, else=3
                    _is_trending = getattr(_regime_snap, "regime", None) and _regime_snap.regime.value in ("TRENDING", "TRENDING_BULL", "TRENDING_BEAR")
                    _max_pos = 5 if _is_trending else 3
                    _strat_pos_count = sum(1 for p in raw_positions
                                          if p.get("symbol", "") == sym
                                          and p.get("comment", "").lower().startswith(_strat_name[:3]))
                    _same_dir_count = sum(1 for p in raw_positions
                                         if p.get("symbol", "") == sym
                                         and p.get("direction", p.get("type", "")).upper() == decision.action.upper())
                    if _strat_pos_count >= _max_pos or _same_dir_count >= _max_pos:
                        log.info(f"MAX_POSITIONS: skip {decision.setup_name} {sym} (strat={_strat_pos_count} dir={_same_dir_count} max={_max_pos})")
                        setup_detail["status"] = "BLOCKED"
                        setup_detail["gate_reason"] = f"max_positions:{_same_dir_count}/{_max_pos}"
                        observatory.log_gate(trace, "MaxPositions", "FAIL", reason=f"dir={_same_dir_count} strat={_strat_pos_count} max={_max_pos}")
                    else:
                        dedup_key = (sym, decision.setup_name, decision.action)
                        now = time.time()
                        last_seen = _seen_setups.get(dedup_key, 0.0)

                        # Adaptive dedup window — M5 candle = 5min minimum
                        # s = SemiHFT -> 300s (1 M5 candle)
                        # a = Aggressive -> 180s
                        # as = both -> 300s
                        # b = Bystra -> 60s (default)
                        _strat_type = decision.setup_name.split("_")[0].lower() if "_" in decision.setup_name else ""
                        _dedup_window = 300 if _strat_type in ("s", "as") else 180 if _strat_type == "a" else DEDUP_WINDOW

                        # Bug fix: actually enforce DEDUP_WINDOW
                        if now - last_seen < _dedup_window:
                            log.info(f"Dedup Time: skip {decision.setup_name} {decision.action} {sym} (cooldown {now - last_seen:.1f}s < {_dedup_window}s)")
                            setup_detail["status"] = "DEDUP"
                            setup_detail["gate_reason"] = f"cooldown_{int(now - last_seen)}s"
                            observatory.log_gate(trace, "Dedup", "FAIL", reason=f"cooldown_{int(now - last_seen)}s")
                            continue

                        # Radius dedup — block if entry within 3.0 points of ANY same-dir position
                        # Bug fix: check _too_close independently (not gated on _any_same_dir)
                        _too_close = any(
                            abs(float(p.get("price", p.get("entry_price", 0))) - price) < 3.0
                            for p in raw_positions
                            if p.get("direction", p.get("type", "")).upper() == decision.action.upper()
                            and p.get("symbol", "") == sym
                        )
                        if _too_close:
                            log.info(f"Dedup Radius: skip {decision.setup_name} {decision.action} {sym} (too close to existing position)")
                            setup_detail["status"] = "DEDUP"
                            setup_detail["gate_reason"] = "price_zone_exists"
                            observatory.log_gate(trace, "Dedup", "FAIL", reason="price_zone_exists")
                            continue

                        # Record AFTER passing dedup (not before gates)
                        _seen_setups[dedup_key] = now
                        
                        # === TRADING INTELLIGENCE GATES ===
                        _blocked = False
                        can_trade, gov_reason = governor.can_trade()
                        if not can_trade:
                            log.info(f"Governor STOP: {gov_reason}")
                            setup_detail["status"] = "GOVERNOR_HALT"
                            setup_detail["gate_reason"] = gov_reason
                            observatory.log_gate(trace, "Governor", "FAIL", reason=gov_reason)
                            _blocked = True

                        # === MOMENTUM GATE — candle must GAS before entry ===
                        if not _blocked:
                            from shared.momentum_gate import check as _mom_check
                            # Exempt mean reversion strategies (SemiHFT, Bystra THREE_CANDLE)
                            setup_key = decision.setup_name.split("_")[0].lower() if "_" in decision.setup_name else decision.setup_name.lower()
                            mean_reversion_setups = {"r", "b"}  # riri_scalps, bystra
                            if setup_key in mean_reversion_setups:
                                _mom = type("_M", (), {"allowed": True, "reason": "mean_reversion_exempt"})()
                            else:
                                _mom = _mom_check(_features, candles, decision.action, setup_name=decision.setup_name)
                            if not _mom.allowed:
                                log.info(f"Momentum Gate: ❌ BLOCK {decision.action} — {_mom.reason}")
                                setup_detail["status"] = "MOMENTUM_BLOCK"
                                setup_detail["gate_reason"] = _mom.reason
                                observatory.log_gate(trace, "Momentum", "FAIL", reason=_mom.reason)
                                _blocked = True

                        # Extract strategy key from setup_name (B_BUY -> bystra, R_BUY -> riri_scalps)
                        strat_key = decision.setup_name.split("_")[0].lower()
                        strat_map = {"b": "bystra", "t": "three_ca", "r": "riri_scalps", "a": "riri_scalps", "s": "riri_scalps", "as": "riri_scalps"}
                        strategy_name = strat_map.get(strat_key, "riri_scalps")
                        if _blocked:
                            log.debug(f"Trade blocked by gate, skipping budget consume")
                        elif not budget_mgr.can_consume(strategy_name):
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
                            if not price or price <= 0:
                                log.warning(f"⚠️ SKIP order {sym} — price fetch returned 0")
                                observatory.log_gate(trace, "Execution", "FAIL", reason="price=0 skip")
                            else:
                                from adapters.broker.models import OrderRequest
                                try:
                                    _entry_mode = decision.metadata.get("entry_mode", "immediate")
                                    _order_type = "limit" if _entry_mode == "retest_c2" else "market"
                                    _ez = decision.metadata.get("entry_zone") or {}
                                    _limit_price = (_ez.get("high") if decision.action == "BUY" else _ez.get("low")) if _order_type == "limit" else None
                                    req = OrderRequest(
                                        symbol=sym,
                                        side=decision.action,
                                        volume=decision.metadata.get("volume", 0.01),
                                        order_type=_order_type,
                                        stop_loss=decision.metadata.get("sl"),
                                        take_profit=decision.metadata.get("take_profit"),
                                        comment=f"TIE_{decision.setup_name}",
                                        metadata={"limit_price": _limit_price, "entry_mode": _entry_mode},
                                    )
                                    resp = broker.submit_order(req)
                                    if resp.status == "FILLED":
                                        log.info(f"✅ ORDER EXECUTED: {sym} {decision.action} {req.volume} lot | SL={req.stop_loss} TP={req.take_profit} ticket={resp.order_id}")
                                        observatory.log_gate(trace, "Execution", "PASS", reason=f"order placed ticket={resp.order_id}")
                                        # monitor.add_setup(decision)  # EntryMonitor disabled — TIE_ path handles tracking
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
                            'early_exit_reversal': False,  # broker SL handles it
                        }
                    })()
            
            if contracts:
                # DISABLED 2026-08-07: manual_trailing_v2 handles all SL/TP trailing
                pass  # pos_monitor.tick(pos_states, contracts, market_update)

            # === BASKET TP (Centralized in Engine) ===
            from shared.basket_manager import process_baskets
            process_baskets(client, pos_states)
            
            # Build pair_data for dashboard
            pair_data = {
                "price": price,
                "support": sr["h1_support"],
                "resistance": sr["h1_resistance"],
                "trend": ctx.trend.value if hasattr(ctx.trend, 'value') else str(ctx.trend),
                "regime": _regime.regime.name if hasattr(_regime, 'regime') else "RANGING",
                "spread": spread,
                "atr": ctx.atr,
                "session": ctx.session.value if hasattr(ctx.session, 'value') else str(ctx.session),
                "last_scan": datetime.now(timezone.utc).isoformat(),
                "setup": setup_detail,
                "vwap_z_score": ctx.vwap_z_score,
            }
            
            all_pairs_data[sym] = pair_data
        
        except Exception as e:
            import traceback
            log.error(f"Error scanning {sym}: {e}\\n{traceback.format_exc()}")
    
    # Write aggregated JSON AFTER all symbols scanned (INSIDE while True loop)
    try:
        write_dashboard_status(all_pairs_data, broker, status_path)
    except Exception as e:
        log.error(f"Dashboard write failed: {e}")
    
    # DISABLED: EntryMonitor submits Riri_ orders — duplicate engine, replaced by TIE_ path
    # monitor.update()

    # === 5 INTELLIGENCE ENGINES ACTIVE ===
    # DISABLED: EntryMonitor removed, counter logic skipped
    # Health check, adaptive learning, optimizer — disabled until reimplemented without monitor dependency

    # Fast pos monitor — tick every 2s x5 instead of sleeping 10s flat
    # Catches BE/trail trigger faster (scalping needs <3s reaction, not 12s)
    _fast_market = {sym: all_pairs_data.get(sym, {}) for sym in SYMBOLS} if 'all_pairs_data' in locals() else {}
    _fast_contracts = contracts if 'contracts' in locals() else {}
    for _ in range(5):
        time.sleep(2)
        try:
            _fast_ps = broker.get_positions()
            if _fast_ps and _fast_contracts:
                _fast_states = [p if isinstance(p, PositionState) else PositionState(
                    position_id=str(getattr(p, 'ticket', getattr(p, 'id', id(p)))),
                    symbol=getattr(p, 'symbol', ''),
                    direction=getattr(p, 'type', getattr(p, 'direction', 'BUY')),
                    entry_price=float(getattr(p, 'price_open', getattr(p, 'entry_price', 0))),
                    current_price=float(getattr(p, 'price_current', getattr(p, 'current_price', 0))),
                    stop_loss=float(getattr(p, 'sl', getattr(p, 'stop_loss', 0)) or 0) or None,
                    take_profit=float(getattr(p, 'tp', getattr(p, 'take_profit', 0)) or 0) or None,
                    volume=float(getattr(p, 'volume', 0)),
                    strategy_id=str(getattr(p, 'comment', 'unknown')).split('_')[0].lower(),
                    unrealized_profit=float(getattr(p, 'profit', getattr(p, 'unrealized_profit', 0))),
                ) for p in _fast_ps]
                # DISABLED 2026-08-07: manual_trailing_v2 handles all SL/TP trailing
                pass  # pos_monitor.tick(_fast_states, _fast_contracts, _fast_market)
        except Exception:
            pass
