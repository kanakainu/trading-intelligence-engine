from typing import Any, Dict, List, Optional, Type
from core.rules.plugins.plugin_interface import RulePluginInterface
from core.rules.plugins.plugin_registry import PluginRegistry

# Import all risk rules
from core.rules.risk.confidence_rule import ConfidenceRule
from core.rules.risk.spread_rule import SpreadRule
from core.rules.risk.rr_rule import RRRule
from core.rules.risk.sl_tp_validation import SLValidationRule, TPValidationRule
from core.rules.risk.session_rule import SessionRule
# Re-use plugins from 5.4
from core.rules.plugins.news_filter import NewsFilterPlugin
from core.rules.plugins.dynamic_lot import DynamicLotPlugin
from core.rules.plugins.adaptive_drawdown import AdaptiveDrawdownPlugin
from core.rules.plugins.daily_target import DailyTargetPlugin


DEFAULT_RISK_RULES: List[tuple] = [
    ("confidence",    ConfidenceRule,         {}),
    ("session",       SessionRule,            {"allowed_sessions": ["LONDON", "NEW_YORK", "ASIA"]}),
    ("spread",        SpreadRule,             {"max_spread": 800}),
    # ("rr",          RRRule,                 {"min_rr": 1.5}),  # REMOVED: RR is SL/TP output, not entry gate (CFD architecture)
    ("sl_validation", SLValidationRule,       {}),
    ("tp_validation", TPValidationRule,       {}),
    ("news",          NewsFilterPlugin,       {"window_minutes": 30}),
    ("drawdown",      AdaptiveDrawdownPlugin, {"limit_pct": 0.30}),
    ("daily_target",  DailyTargetPlugin,      {"target_usd": 30.0}),
    ("lot",           DynamicLotPlugin,       {"min_lot": 0.01, "max_lot": 0.3, "risk_pct": 0.03}),
]


def build_risk_registry(overrides: Optional[Dict[str, Dict]] = None) -> PluginRegistry:
    """Build a PluginRegistry with all default risk rules."""
    reg = PluginRegistry()
    for name, cls, default_cfg in DEFAULT_RISK_RULES:
        cfg = {**default_cfg, **(overrides or {}).get(name, {})}
        plugin = cls()
        plugin.initialize(cfg)
        reg.register(name, plugin)
    return reg
