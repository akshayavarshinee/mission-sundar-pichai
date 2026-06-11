"""The adaptive eval-gate: an *independent* oracle, a judge that learns from real
destination outcomes, and the "evaluate the evaluator" harness that proves it
improves with experience.

These pin the properties that make the eval non-circular and the learning real:

* the oracle rejects declarations the carrier's own ``policy_lint`` passes (it
  models destination rules the carrier never enforces), so judge-vs-oracle is
  not the gate grading itself;
* the learned judge ``abstain``s when cold (so an untrained gate behaves exactly
  as before) and comes to ``veto`` once it has independently-adjudicated
  precedent — with no hard-coded rule;
* enabling the learned judge only ever *tightens* the gate;
* the judge-eval learning curve shows accuracy rising and false-auto-clear
  falling as experience accumulates, and registers a real Phoenix experiment
  whose task actually runs the judge.

All offline and deterministic (conftest pins local embeddings + no creds).
"""

from __future__ import annotations

import pytest

from clearport.config import settings
from clearport.eval.learned_judge import LearnedJudge
from clearport.eval.oracle import (
    DEST_ACCEPTED_HEADINGS,
    IndependentOracle,
    destination_registry_check,
    features_of,
)
from clearport.memory.adjudications import AdjudicationStore
from clearport.schemas import (
    Adjudication,
    ContentsType,
    CustomsItemSpec,
    CustomsPayload,
    NormalizedErrorType,
    OracleSource,
    PatchProposal,
    RawError,
    RejectionEvent,
    Source,
)
from clearport.seeds.shipments import LANE_IN_US
from clearport.validation.errors import hs_is_valid, policy_lint

# A syntactically-valid HS whose 4-digit heading (9403) is NOT on the
# destination's accepted schedule — carrier-clean but destination-rejected.
_RESTRICTED_HS = "940360"
_RESTRICTED_HEADING = "9403"
# An accepted line (heading 8302 is on the schedule).
_ACCEPTED_HS = "830249"


def _payload(
    *,
    hs: str = _ACCEPTED_HS,
    signer: str = "Anaya Sharma",
    value: float = 120.0,
    quantity: int = 2,
    desc: str = "Hand-engraved brass keychain",
) -> CustomsPayload:
    return CustomsPayload(
        contents_type=ContentsType.MERCHANDISE,
        customs_certify=True,
        customs_signer=signer,
        items=[
            CustomsItemSpec(
                description=desc,
                quantity=quantity,
                value=value,
                weight_oz=10.0,
                origin_country="IN",
                hs_tariff_number=hs,
            )
        ],
    )


# ── oracle independence (it is NOT policy_lint) ──────────────────────────────
def test_restricted_heading_is_carrier_clean_but_destination_rejected() -> None:
    payload = _payload(hs=_RESTRICTED_HS)
    # The carrier accepts it: valid syntax, full signer, plausible value.
    assert hs_is_valid(_RESTRICTED_HS)
    assert policy_lint(payload) is None
    # The destination registry — a different authority — rejects it.
    assert _RESTRICTED_HEADING not in DEST_ACCEPTED_HEADINGS
    accepted, detail = destination_registry_check(payload, LANE_IN_US)
    assert accepted is False
    assert _RESTRICTED_HEADING in detail


def test_oracle_rejects_stub_signer_that_carrier_accepts() -> None:
    payload = _payload(signer="Anaya")  # single token: carrier-clean, dest-rejects
    assert policy_lint(payload) is None
    adj = IndependentOracle().adjudicate(
        payload, lane=LANE_IN_US, error_type=NormalizedErrorType.SIGNER_MISSING
    )
    assert adj.accepted is False
    assert adj.source is OracleSource.DESTINATION_REGISTRY


def test_oracle_rejects_undervalued_line_that_carrier_accepts() -> None:
    payload = _payload(value=1.50, quantity=1)  # unit value below the dest floor
    assert policy_lint(payload) is None
    accepted, _ = destination_registry_check(payload, LANE_IN_US)
    assert accepted is False


def test_oracle_accepts_a_genuinely_clean_declaration() -> None:
    payload = _payload()
    assert policy_lint(payload) is None
    adj = IndependentOracle().adjudicate(payload, lane=LANE_IN_US)
    assert adj.accepted is True
    assert adj.source is OracleSource.DESTINATION_REGISTRY
    assert adj.features  # an embeddable retrieval key was captured


# ── adjudication store (the experience corpus) ───────────────────────────────
def _teach(store: AdjudicationStore, hs: str, *, accepted: bool, n: int = 6) -> None:
    """Add ``n`` independently-adjudicated outcomes for one HS heading."""
    descs = [
        "Hand-engraved brass keychain",
        "Glazed porcelain teacup set",
        "Woven wicker basket set",
        "Cotton knit t-shirt (lot)",
        "Hand-block-printed silk scarf",
        "Whole black peppercorn sampler",
    ]
    for i in range(n):
        payload = _payload(hs=hs, desc=descs[i % len(descs)])
        store.add(
            Adjudication(
                memory_key=f"test|{hs}",
                error_type=NormalizedErrorType.UNKNOWN,
                accepted=accepted,
                source=OracleSource.DESTINATION_REGISTRY,
                detail="destination outcome",
                features=features_of(payload, NormalizedErrorType.UNKNOWN),
            )
        )


def test_adjudication_store_roundtrips_and_searches() -> None:
    store = AdjudicationStore()
    _teach(store, _RESTRICTED_HS, accepted=False, n=3)
    assert store.count() == 3
    probe = features_of(_payload(hs=_RESTRICTED_HS), NormalizedErrorType.UNKNOWN)
    hits = store.search(probe, k=3)
    assert hits
    adj, score = hits[0]
    assert isinstance(adj, Adjudication)
    assert 0.0 <= score <= 1.0


# ── learned judge: abstains cold, learns with experience ─────────────────────
def test_learned_judge_abstains_when_cold() -> None:
    judge = LearnedJudge(store=AdjudicationStore())
    verdict = judge.assess(
        features_of(_payload(hs=_RESTRICTED_HS), NormalizedErrorType.UNKNOWN),
        NormalizedErrorType.UNKNOWN,
    )
    assert verdict.vote == "abstain"
    assert verdict.neighbors_used == 0
    assert verdict.is_veto is False


def test_learned_judge_abstains_below_minimum_evidence() -> None:
    store = AdjudicationStore()
    _teach(store, _RESTRICTED_HS, accepted=False, n=1)  # < min_evidence (3)
    judge = LearnedJudge(store=store)
    verdict = judge.assess(
        features_of(_payload(hs=_RESTRICTED_HS), NormalizedErrorType.UNKNOWN),
        NormalizedErrorType.UNKNOWN,
    )
    assert verdict.vote == "abstain"


def test_learned_judge_learns_to_veto_a_restricted_heading() -> None:
    store = AdjudicationStore()
    _teach(store, _RESTRICTED_HS, accepted=False, n=6)
    judge = LearnedJudge(store=store)
    verdict = judge.assess(
        features_of(_payload(hs=_RESTRICTED_HS), NormalizedErrorType.UNKNOWN),
        NormalizedErrorType.UNKNOWN,
    )
    assert verdict.is_veto is True
    assert verdict.source == "knn"
    assert verdict.neighbors_used >= settings.clearport_learned_judge_min_evidence
    # Confidence is evidence-derived (neighbour agreement), not a model self-report.
    assert verdict.confidence >= settings.clearport_learned_judge_veto_fraction


def test_learned_judge_accepts_with_positive_precedent() -> None:
    store = AdjudicationStore()
    _teach(store, _ACCEPTED_HS, accepted=True, n=6)
    judge = LearnedJudge(store=store)
    verdict = judge.assess(
        features_of(_payload(hs=_ACCEPTED_HS), NormalizedErrorType.UNKNOWN),
        NormalizedErrorType.UNKNOWN,
    )
    assert verdict.vote == "accept"
    assert verdict.is_veto is False


# ── judge integration: only ever tightens, unchanged when cold ───────────────
def _rejection(hs: str) -> RejectionEvent:
    return RejectionEvent(
        source=Source.COMPLIANCE,
        lane=LANE_IN_US,
        persona="test shipper",
        payload=_payload(hs=hs),
        raw_error=RawError(code="X", message="[test]"),
        normalized_error_type=NormalizedErrorType.HS_INVALID,
    )


def _patch(rejection: RejectionEvent) -> PatchProposal:
    # A clean patched declaration (the carrier would accept it as-is).
    return PatchProposal(rejection_id=rejection.id, patched_payload=rejection.payload)


def test_gate_unchanged_when_store_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    # Even with the learned judge enabled, a cold store must leave a clean,
    # carrier-valid patch PASSING — i.e. exactly the pre-learning behaviour.
    monkeypatch.setattr(settings, "clearport_learned_judge", "on", raising=False)
    from clearport.eval.judge import Judge

    rejection = _rejection(_ACCEPTED_HS)
    verdict = Judge(learned=LearnedJudge(store=AdjudicationStore())).evaluate(
        rejection, _patch(rejection)
    )
    assert verdict.passed is True
    assert verdict.judge_model == "deterministic-policy"
    assert verdict.learned is not None and verdict.learned.vote == "abstain"


def test_learned_veto_tightens_an_otherwise_passing_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "clearport_learned_judge", "on", raising=False)
    from clearport.eval.judge import Judge

    store = AdjudicationStore()
    _teach(store, _RESTRICTED_HS, accepted=False, n=6)
    rejection = _rejection(_RESTRICTED_HS)
    patch = _patch(rejection)
    # The carrier-side deterministic gate would pass this declaration…
    assert policy_lint(patch.patched_payload) is None
    verdict = Judge(learned=LearnedJudge(store=store)).evaluate(rejection, patch)
    # …but learned precedent flips it to FAIL (a destination rule the carrier missed).
    assert verdict.passed is False
    assert verdict.learned is not None and verdict.learned.is_veto
    assert "+learned:knn" in verdict.judge_model
    assert verdict.rubric.law_consistent is False


def test_learned_judge_is_off_by_default_offline() -> None:
    # The whole suite runs offline; the adaptive judge must default to OFF so the
    # baseline loop/tests are unaffected until Phoenix (or an explicit on) is set.
    assert settings.learned_judge_enabled is False


# ── "evaluate the evaluator": the learning curve ─────────────────────────────
def test_judge_eval_improves_with_experience() -> None:
    from clearport.eval.judge_eval import run_judge_eval

    report = run_judge_eval(n_test_per_slice=8, n_train_per_slice=12, seed=11)
    # The judge ends up tracking the independent oracle and never auto-clears a
    # destination-rejected declaration once fully taught.
    assert report.false_auto_clear_rate == 0.0
    assert report.accuracy >= 0.9
    # It genuinely improved from cold to taught.
    assert report.improvement > 0.0
    curve = report.learning_curve
    assert len(curve) >= 2
    assert curve[0].n_adjudications == 0
    # Cold judge auto-clears the restricted half; experience drives that to zero.
    assert curve[0].false_auto_clear_rate > 0.0
    assert curve[-1].false_auto_clear_rate == 0.0
    # Accuracy is monotonically non-decreasing along the experience stream.
    accuracies = [p.accuracy for p in curve]
    assert accuracies == sorted(accuracies)
    assert accuracies[-1] >= accuracies[0]


# ── Phoenix registration (opt-in, fake client; task RUNS the judge) ──────────
class _FakeExperiments:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run_experiment(self, *, dataset, task, evaluators, **kw):  # noqa: ANN001, ANN003
        # Exercise the real task on every example so we prove it runs the judge
        # (not a label echo) and that the evaluators score against the oracle.
        rows = [task(ex["input"]) for ex in dataset.examples]
        self.calls.append({"evaluators": evaluators, "rows": rows, "kw": kw})
        return {"experiment_id": "exp-judge-7"}


class _FakeDataset:
    def __init__(self, inputs: list[dict], id: str = "ds-judge-1") -> None:  # noqa: A002
        self.example_count = len(inputs)
        self.id = id
        self.examples = [{"input": row} for row in inputs]


class _FakeDatasets:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create_dataset(self, *, name, inputs, outputs, metadata, **kw):  # noqa: ANN001, ANN003
        self.calls.append({"name": name, "inputs": inputs})
        return _FakeDataset(inputs)


class _FakeClient:
    def __init__(self) -> None:
        self.experiments = _FakeExperiments()
        self.datasets = _FakeDatasets()


def test_judge_eval_registers_phoenix_experiment_when_forced() -> None:
    from clearport.eval.judge_eval import run_judge_eval

    fake = _FakeClient()
    report = run_judge_eval(register_phoenix=True, phoenix_client=fake)
    assert report.experiment_live is True
    assert report.experiment_id == "exp-judge-7"
    assert report.experiment_dataset_id == "ds-judge-1"
    evaluators = fake.experiments.calls[0]["evaluators"]
    assert {"agrees_with_oracle", "no_false_auto_clear"} <= set(evaluators)
    # The task actually ran the judge for every example (real decisions, no echo).
    rows = fake.experiments.calls[0]["rows"]
    assert rows and all("judge_accepted" in r for r in rows)
