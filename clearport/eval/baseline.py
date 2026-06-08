"""Accepted-baseline management (memory tier ② as the eval reference set).

The judge compares each patch against *historically accepted* shipments. We seed
that baseline by running the agent's own correct fixes on the failing seeds (plus
the clean control), validating that each corrected payload passes policy lint,
and storing it as an accepted episodic example. At runtime the baseline is read
back via :func:`get_baseline` (in-memory or Phoenix dataset over MCP).
"""

from __future__ import annotations

import structlog

from clearport.memory.episodic import EpisodicMemory, get_episodic
from clearport.schemas import CustomsPayload, NormalizedErrorType
from clearport.validation.errors import policy_lint

logger = structlog.get_logger(__name__)


def _summary(payload: CustomsPayload, error_type: str) -> str:
    items = ", ".join(f"{i.description} (HTS {i.hs_tariff_number})" for i in payload.items)
    return f"accepted[{error_type}] value=${payload.total_value:.2f} items={items}"


def accepted_example(payload: CustomsPayload, error_type: NormalizedErrorType) -> tuple[dict, dict, dict]:
    """Build an (input, output, metadata) accepted episodic example."""
    input_ = {
        "summary": _summary(payload, error_type.value),
        "payload": payload.model_dump(mode="json"),
    }
    output = {"accepted": True}
    metadata = {"accepted": "true", "error_type": error_type.value, "kind": "baseline"}
    return input_, output, metadata


def seed_default_baseline(episodic: EpisodicMemory | None = None) -> int:
    """Populate the accepted baseline from the agent's own correct fixes."""
    # Imported here to avoid a circular import (agents -> eval at module load).
    from clearport.agents.auditor import Auditor
    from clearport.agents.patch_engine import PatchEngine
    from clearport.memory.recall import recall
    from clearport.seeds.shipments import all_seeds
    from clearport.validation.harness import run_seed

    episodic = episodic or get_episodic()
    auditor, patcher = Auditor(), PatchEngine()
    count = 0

    for seed in all_seeds():
        if seed.expected_error is None:
            # clean control is accepted as-is
            in_, out_, meta = accepted_example(seed.payload, NormalizedErrorType.UNKNOWN)
            meta["error_type"] = "CONTROL"
            episodic.add_example(in_, out_, meta)
            count += 1
            continue

        rejection = run_seed(seed)
        if rejection is None:
            continue
        memory = recall(rejection, episodic=episodic)
        diagnosis = auditor.diagnose(rejection, memory)
        patch = patcher.patch(rejection, diagnosis)
        corrected = patch.patched_payload
        # Only store as "accepted" if the corrected payload truly passes the rules
        # (EEI patches intentionally remain human-gated and are skipped here).
        if policy_lint(corrected) is None:
            in_, out_, meta = accepted_example(corrected, rejection.normalized_error_type)
            episodic.add_example(in_, out_, meta)
            count += 1

    logger.info("baseline.seeded", accepted=count)
    return count


def get_baseline(
    error_type: NormalizedErrorType | None = None,
    k: int = 20,
    episodic: EpisodicMemory | None = None,
) -> list[dict]:
    episodic = episodic or get_episodic()
    return episodic.baseline_examples(error_type.value if error_type else None, k=k)
