"""The four ClearPort agents + the recovery loop.

    Orchestrator   — plans/drives the loop (orchestrator.py + adk_app.py)
    Customs Auditor — diagnoses, grounded by tiered memory (auditor.py)
    Patch Engine   — rewrites the immutable declaration (patch_engine.py)
    Self-Healer    — eval-gate, risk tier, learning, drift (eval/ + arize/)

``classifier.py`` is a complementary HS-classification tool the Auditor/Patch
Engine may call (we orchestrate; we do not reinvent classification).
"""
