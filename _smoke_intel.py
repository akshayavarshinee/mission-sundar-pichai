import json

from clearport.config import settings

# Force the fully-offline, deterministic path for a fast smoke test.
settings.easypost_api_key = None
settings.google_api_key = None
settings.google_genai_use_vertexai = False
settings.google_cloud_project = None
settings.clearport_episodic_backend = "memory"
settings.clearport_prompts_backend = "local"
settings.clearport_vector_backend = "memory"
settings.clearport_embeddings_backend = "local"

from clearport.api.demo_runner import play_scripted_demo
from clearport.api.intelligence import compute_intelligence
from clearport.service import get_service

svc = get_service()
play_scripted_demo(svc)
d = compute_intelligence(svc).model_dump()

print("progression points:", len(d["progression"]))
print(
    "memory:",
    "lessons", d["memory"]["lessons_count"],
    "episodic", d["memory"]["episodic_total"],
    "law", d["memory"]["law_count"],
)
print("tiers:", [(t["tier"], t["count"], t["backend"]) for t in d["memory"]["tiers"]])
print("eval_gate:", d["arize"]["eval_gate"])
print("spans:", d["arize"]["spans_emitted"], "traces:", d["arize"]["traces_emitted"])
print("datasets:", d["arize"]["datasets"])
print("self_heal:", json.dumps(d["self_heal"], indent=2))
print("lesson_timeline:", json.dumps(d["lesson_timeline"], indent=2))
print("last_prog:", json.dumps(d["progression"][-1], indent=2))
