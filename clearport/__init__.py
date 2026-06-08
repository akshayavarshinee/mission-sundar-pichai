"""ClearPort — autonomous customs-recovery agent.

An agent that heals rejected cross-border customs declarations, using Arize
Phoenix as an evaluation conscience that must approve every fix against
historically-accepted shipments before any real-money action is taken.

Package layout:
    clearport.agents      — Orchestrator + Auditor + Patch Engine + Self-Healer
    clearport.memory      — tiered memory (Design B): law / episodic / lessons / prompts
    clearport.validation  — EasyPost (real) + Regional Rule Overlay (drift) surfaces
    clearport.eval        — LLM-as-judge, risk tier, promotion experiments
    clearport.arize       — Phoenix MCP client, OTel tracing, drift monitor
    clearport.api         — FastAPI backend + live event stream + approvals
    clearport.schemas     — pydantic data contracts shared across phases
    clearport.seeds       — demo seed shipments (S1-S4 + wildcard) + curated KB
"""

__version__ = "0.1.0"
