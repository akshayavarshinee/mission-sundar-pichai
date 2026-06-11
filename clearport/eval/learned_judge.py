"""The learned judge — the part of the eval-gate that improves over time.

Given a declaration the carrier already accepts, this predicts whether the
*destination* will accept it, by generalising from semantically-similar past
adjudications (real destination outcomes). Two interchangeable backends:

* **offline / no-keys** — instance-based (k-nearest-neighbour) over the
  adjudication embeddings: a similarity-weighted vote of the neighbours' real
  outcomes. Genuinely improves as the corpus grows; nothing is hard-coded.
* **live (Gemini)** — the same neighbours are supplied to Gemini as few-shot
  exemplars (in-context learning), so the model's judgement sharpens with
  experience without any retraining.

Either way the verdict can only ever *tighten* the deterministic gate: a
confident ``veto`` blocks an auto-clear the policy lint would have allowed (a
destination rule the carrier never checks), while ``accept`` / ``abstain`` leave
the gate untouched. With an empty or thin corpus the judge ``abstain``s, so the
gate behaves exactly as it did before it had learned anything.
"""

from __future__ import annotations

import structlog

from clearport import llm
from clearport.config import settings
from clearport.schemas import Adjudication, LearnedVerdict, NormalizedErrorType

logger = structlog.get_logger(__name__)


class LearnedJudge:
    """Predicts the destination verdict from adjudicated experience."""

    def __init__(self, store=None) -> None:  # noqa: ANN001 — AdjudicationStore | None
        self._store = store

    @property
    def store(self):  # noqa: ANN201 — AdjudicationStore (lazy, shared by default)
        if self._store is None:
            from clearport.memory.adjudications import get_adjudications

            self._store = get_adjudications()
        return self._store

    def assess(
        self,
        features: str,
        error_type: NormalizedErrorType,
        *,
        k: int | None = None,
    ) -> LearnedVerdict:
        """Return the learned opinion for a case described by ``features``."""
        k = k or settings.clearport_learned_judge_k
        # Retrieve neighbours across all error types (a destination rule — e.g. an
        # unaccepted tariff heading — recurs regardless of the original rejection
        # reason), then keep those above the similarity floor.
        neighbours = [
            (adj, sim)
            for adj, sim in self.store.search(features, k=k)
            if sim >= settings.clearport_learned_judge_min_similarity
        ]
        if len(neighbours) < settings.clearport_learned_judge_min_evidence:
            return LearnedVerdict(
                vote="abstain",
                basis=(
                    f"only {len(neighbours)} relevant adjudication(s) "
                    f"(need {settings.clearport_learned_judge_min_evidence})"
                ),
                neighbors_used=len(neighbours),
                source="none",
            )

        weighted_reject, weighted_total = self._weighted_reject(neighbours)
        reject_fraction = weighted_reject / weighted_total if weighted_total else 0.0
        accept_fraction = 1.0 - reject_fraction
        evidence_conf = round(max(reject_fraction, accept_fraction), 3)

        # Offline (or on any model failure) the kNN vote stands; live, Gemini
        # decides using the same neighbours as exemplars. Confidence stays
        # evidence-derived (neighbour agreement), never the model's self-report.
        vote, basis, source = self._knn_vote(reject_fraction, neighbours)
        if self._llm_enabled():
            try:
                llm_vote, llm_basis = self._llm_vote(features, neighbours)
                vote, basis, source = llm_vote, llm_basis, "llm"
            except llm.LLMUnavailable:
                pass
            except Exception as exc:  # noqa: BLE001 — fall back to the kNN vote
                logger.warning("learned_judge.llm_failed", error=str(exc))

        verdict = LearnedVerdict(
            vote=vote,
            confidence=evidence_conf,
            basis=basis,
            neighbors_used=len(neighbours),
            source=source,
        )
        logger.info(
            "learned_judge.assess",
            vote=vote,
            confidence=evidence_conf,
            neighbours=len(neighbours),
            reject_fraction=round(reject_fraction, 3),
            source=source,
        )
        return verdict

    # ── kNN (instance-based) backend ─────────────────────────────────────
    @staticmethod
    def _weighted_reject(
        neighbours: list[tuple[Adjudication, float]],
    ) -> tuple[float, float]:
        weighted_reject = sum(sim for adj, sim in neighbours if not adj.accepted)
        weighted_total = sum(sim for _adj, sim in neighbours)
        return weighted_reject, weighted_total

    def _knn_vote(
        self, reject_fraction: float, neighbours: list[tuple[Adjudication, float]]
    ) -> tuple[str, str, str]:
        veto_fraction = settings.clearport_learned_judge_veto_fraction
        n = len(neighbours)
        if reject_fraction >= veto_fraction:
            return (
                "veto",
                f"{reject_fraction:.0%} of {n} similar adjudicated declarations were "
                "rejected by the destination",
                "knn",
            )
        if (1.0 - reject_fraction) >= veto_fraction:
            return (
                "accept",
                f"{(1.0 - reject_fraction):.0%} of {n} similar adjudicated declarations "
                "were accepted by the destination",
                "knn",
            )
        return (
            "abstain",
            f"mixed precedent across {n} similar adjudications "
            f"({reject_fraction:.0%} rejected)",
            "knn",
        )

    # ── live LLM (in-context learning) backend ───────────────────────────
    @staticmethod
    def _llm_enabled() -> bool:
        return settings.learned_judge_enabled and llm.is_live()

    @staticmethod
    def _llm_vote(
        features: str, neighbours: list[tuple[Adjudication, float]]
    ) -> tuple[str, str]:
        """Ask Gemini to predict the destination verdict from few-shot precedent."""
        from clearport.memory.prompts import get_prompt

        exemplars = "\n".join(
            f"- [{'ACCEPTED' if adj.accepted else 'REJECTED'}] {adj.features}"
            + (f" — {adj.detail}" if adj.detail else "")
            for adj, _sim in neighbours
        )
        user = (
            "Past declarations and whether the DESTINATION gateway accepted them "
            "(most similar first):\n"
            f"{exemplars}\n\n"
            "New declaration the carrier already accepts:\n"
            f"{features}\n\n"
            "Using the precedent above, will the destination accept the new "
            'declaration? Respond ONLY as JSON: {"vote": "accept"|"veto", '
            '"reason": "..."}. Answer "veto" only if precedent indicates the '
            "destination would reject it."
        )
        data = llm.generate_json(get_prompt("judge"), user, temperature=0.0)
        raw = str(data.get("vote", "")).strip().lower()
        vote = "veto" if raw == "veto" else "accept"
        reason = str(data.get("reason", "")).strip()
        return vote, reason or "Gemini few-shot prediction from adjudicated precedent."
