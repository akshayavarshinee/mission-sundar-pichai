"""Phase 2 unit tests: the law VETO over learned lessons + tiered recall."""

from __future__ import annotations

from clearport.memory.law_store import law_veto
from clearport.memory.lessons import LessonsStore
from clearport.memory.recall import recall
from clearport.schemas import DistilledLesson, MemoryKey, NormalizedErrorType
from clearport.seeds.shipments import get_seed
from clearport.validation.harness import run_seed


def _lesson(error_type: NormalizedErrorType, fix: str, hs: str = "61") -> DistilledLesson:
    return DistilledLesson(
        key=MemoryKey(lane="IN->US", hs_chapter=hs, error_type=error_type),
        pattern="learned pattern",
        recommended_fix=fix,
    )


def test_law_veto_blocks_noeei_over_threshold() -> None:
    payload = get_seed("S2").payload  # value 3200, >= $2,500
    bad = _lesson(NormalizedErrorType.EEI_THRESHOLD_MISMATCH, "just use NOEEI 30.37(a)")
    good = _lesson(NormalizedErrorType.EEI_THRESHOLD_MISMATCH, "file an EEI/AES ITN")
    assert law_veto(bad, payload)[0] is True
    assert law_veto(good, payload)[0] is False


def test_law_veto_blocks_invalid_hs() -> None:
    payload = get_seed("S1").payload
    bad = _lesson(NormalizedErrorType.HS_INVALID, "classify as 1234", hs="83")
    good = _lesson(NormalizedErrorType.HS_INVALID, "classify as 830249", hs="83")
    assert law_veto(bad, payload)[0] is True
    assert law_veto(good, payload)[0] is False


def test_recall_keeps_lawful_lesson_and_vetoes_unlawful() -> None:
    store = LessonsStore()
    bad = _lesson(NormalizedErrorType.EEI_THRESHOLD_MISMATCH, "use NOEEI 30.37(a) to clear fast")
    good = _lesson(
        NormalizedErrorType.EEI_THRESHOLD_MISMATCH,
        "file EEI/AES ITN because value is at or above 2500",
    )
    store.add(bad)
    store.add(good)

    rejection = run_seed(get_seed("S2"))
    assert rejection is not None

    memory = recall(rejection, lessons_store=store)
    kept_ids = {lesson_ref.lesson_id for lesson_ref in memory.lessons}

    assert good.id in kept_ids
    assert bad.id in memory.vetoed_lesson_ids
    assert bad.id not in kept_ids
    assert len(memory.law_citations) >= 1


def test_recall_attaches_law_citations_offline() -> None:
    rejection = run_seed(get_seed("S1"))
    assert rejection is not None
    memory = recall(rejection)
    assert memory.law_citations  # grounding present even with no lessons
