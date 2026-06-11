"""Temporary offline smoke test for seed_rich_history (deleted after use)."""

from clearport.config import settings

settings.easypost_api_key = ""
settings.google_api_key = ""
settings.google_genai_use_vertexai = False
settings.clearport_embeddings_backend = "local"
settings.clearport_episodic_backend = "memory"
settings.clearport_prompts_backend = "local"

from clearport import llm  # noqa: E402

llm.is_live = lambda: False

from clearport.api.intelligence import compute_intelligence  # noqa: E402
from clearport.api.seed_history import seed_rich_history  # noqa: E402
from clearport.service import ClearPortService  # noqa: E402

svc = ClearPortService()
s = seed_rich_history(svc)
r = compute_intelligence(svc)

print("runs_made:", s["runs_made"], "| lessons_promoted:", s["lessons_promoted"])
print("progression points:", len(r.progression))
print("lessons_count:", r.memory.lessons_count)
print(
    "episodic total/outcomes/corrections/accepted:",
    r.memory.episodic_total,
    r.memory.episodic_outcomes,
    r.memory.episodic_corrections,
    r.memory.episodic_accepted,
)
print("self_heal pairs:", len(r.self_heal))
for p in r.self_heal:
    print("   ", p.error_type, "occ", p.occurrences, "healed", p.healed_from_memory, "speedup", p.speedup)
print(
    "eval_gate total/passed/failed/rate:",
    r.arize.eval_gate.total,
    r.arize.eval_gate.passed,
    r.arize.eval_gate.failed,
    r.arize.eval_gate.pass_rate,
)
if r.progression:
    print("cum_auto_pct first->last:", r.progression[0].cum_auto_pct, "->", r.progression[-1].cum_auto_pct)
    print("cum_lessons last:", r.progression[-1].cum_lessons)
print("lesson_timeline:", len(r.lesson_timeline))
print("arize exp_won/traces/spans:", r.arize.experiments_won, r.arize.traces_emitted, r.arize.spans_emitted)
print("memory tiers:", [(t.tier, t.name, t.count) for t in r.memory.tiers])
