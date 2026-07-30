import pytest, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from skills.registry import SkillRegistry
from skills.manager import SkillManager
from skills.pipeline import SkillPipeline
from skills.context import SkillContext
from skills.builtins.session_skill import SessionSkill, TrendSkill, VolatilitySkill, LiquiditySkill


def test_skill_registration():
    reg = SkillRegistry()
    reg.register("session", SessionSkill)
    assert "session" in reg.list_available()


def test_skill_execution():
    reg = SkillRegistry()
    reg.register("session", SessionSkill)
    mgr = SkillManager(reg)
    mgr.load_skill("session")
    
    ctx = SkillContext(market_snapshot={"price": 2000.0})
    res = mgr.execute_skill("session", ctx)
    
    assert res.success
    assert "session" in res.findings


def test_pipeline_execution():
    reg = SkillRegistry()
    reg.register("session", SessionSkill)
    reg.register("trend", TrendSkill)
    mgr = SkillManager(reg)
    mgr.load_skill("session")
    mgr.load_skill("trend")
    
    pipe = SkillPipeline(mgr)
    pipe.add_step("session")
    pipe.add_step("trend")
    
    ctx = SkillContext(market_snapshot={"price": 2000.0})
    results = pipe.execute(ctx)
    
    assert len(results) == 2
    assert results[0].skill_name == "session"
    assert results[1].skill_name == "trend"


def test_health_report():
    reg = SkillRegistry()
    reg.register("session", SessionSkill)
    mgr = SkillManager(reg)
    mgr.load_skill("session")
    
    report = mgr.get_health_report()
    assert "session" in report["loaded_skills"]
    assert report["status"] == "OPERATIONAL"
