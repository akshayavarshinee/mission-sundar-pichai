"""Judge-quality evaluation — does the *evaluator* track independent truth, and
does it get better with experience?

This is the meta-eval the Arize partner track is built around: we don't just run
the agent, we **evaluate the evaluator**. A labelled suite of carrier-clean
declarations is judged for *destination* acceptance; the gate's decision (policy
lint + the learned judge) is scored against the :mod:`clearport.eval.oracle`
ground truth — a source the gate never uses, so the numbers are not circular.

The headline artifact is the **learning curve**: starting from a cold judge, we
feed progressively more independently-adjudicated precedent and re-measure. As
the judge accumulates experience it learns to anticipate destination rejections
the carrier-side lint cannot see — accuracy rises and the false-auto-clear rate
falls. With Phoenix live the suite is registered as a real experiment whose task
*actually runs the judge* and whose evaluator scores against the oracle (no
label echo), so the improvement is clickable in Phoenix.
"""

from __future__ import annotations

import random

import structlog

from clearport.config import settings
from clearport.eval.learned_judge import LearnedJudge
from clearport.eval.oracle import IndependentOracle, features_of, get_oracle
from clearport.memory.adjudications import AdjudicationStore
from clearport.schemas import (
    Adjudication,
    ContentsType,
    CustomsItemSpec,
    CustomsPayload,
    JudgeCaseResult,
    JudgeEvalReport,
    LearningCurvePoint,
    NormalizedErrorType,
    new_id,
)
from clearport.seeds.shipments import LANE_IN_US
from clearport.validation.errors import policy_lint

logger = structlog.get_logger(__name__)

# Carrier-clean declarations whose only variable is a *destination* property.
# Accepted tariff lines (heading on the destination's approved schedule).
_ACCEPTED_HS = ["830249", "621440", "610910", "090411", "460219", "691110"]
# Syntactically-valid HS whose 4-digit heading is NOT on the destination schedule
# — carrier-clean, destination-rejected (the silent-rule surface).
_RESTRICTED_HS = ["940360", "842139", "732690", "392690", "871200"]
_DESCS = [
    "Hand-engraved brass keychain",
    "Hand-block-printed silk scarf",
    "Cotton knit t-shirt (lot)",
    "Whole black peppercorn sampler",
    "Woven wicker basket set",
    "Glazed porcelain teacup set",
]
_FULL_SIGNERS = ["Anaya Sharma", "Ravi Menon", "Priya Nair", "Arjun Rao", "Meera Iyer"]
_STUB_SIGNERS = ["Anaya", "Ravi", "Priya", "A.", "RM"]


def _item(desc: str, hs: str, value: float, *, quantity: int = 2, weight_oz: float = 10.0) -> CustomsItemSpec:
    return CustomsItemSpec(
        description=desc,
        quantity=quantity,
        value=value,
        weight_oz=weight_oz,
        origin_country="IN",
        hs_tariff_number=hs,
    )


def _payload(item: CustomsItemSpec, *, signer: str) -> CustomsPayload:
    return CustomsPayload(
        contents_type=ContentsType.MERCHANDISE,
        customs_certify=True,
        customs_signer=signer,
        items=[item],
    )


def _gen(slice_name: str, idx: int, rng: random.Random) -> CustomsPayload:
    """Build one carrier-clean declaration for a destination slice."""
    desc = _DESCS[idx % len(_DESCS)]
    plausible = round(rng.uniform(60.0, 900.0), 2)  # unit value comfortably > floor

    if slice_name == "dest_accept":
        return _payload(_item(desc, _ACCEPTED_HS[idx % len(_ACCEPTED_HS)], plausible), signer=rng.choice(_FULL_SIGNERS))
    if slice_name == "dest_hs_restricted":
        return _payload(_item(desc, _RESTRICTED_HS[idx % len(_RESTRICTED_HS)], plausible), signer=rng.choice(_FULL_SIGNERS))
    if slice_name == "dest_signer_stub":
        return _payload(_item(desc, _ACCEPTED_HS[idx % len(_ACCEPTED_HS)], plausible), signer=_STUB_SIGNERS[idx % len(_STUB_SIGNERS)])
    if slice_name == "dest_undervalued":
        # qty 1 so the line total *is* the (implausibly low) unit value.
        return _payload(_item(desc, _ACCEPTED_HS[idx % len(_ACCEPTED_HS)], round(rng.uniform(0.5, 2.5), 2), quantity=1, weight_oz=4.0), signer=rng.choice(_FULL_SIGNERS))
    raise ValueError(f"unknown slice {slice_name!r}")  # pragma: no cover


class _Case:
    """A judge-eval case: a declaration + its independent oracle label."""

    def __init__(self, case_id: str, slice_name: str, payload: CustomsPayload, oracle_accepted: bool) -> None:
        self.case_id = case_id
        self.slice = slice_name
        self.payload = payload
        self.oracle_accepted = oracle_accepted
        self.features = features_of(payload, NormalizedErrorType.UNKNOWN)


def _build_cases(prefix: str, n_per_slice: int, seed: int, oracle: IndependentOracle) -> list[_Case]:
    rng = random.Random(seed)
    cases: list[_Case] = []
    # Balanced suite focused on the canonical silent-rule surface: the destination
    # quietly restricts which tariff *headings* it accepts. Accept and reject
    # cases draw from the SAME descriptions, signers, and value distribution, so
    # the only label-correlated signal is the HS heading — exactly what the judge
    # must learn from experience (there is no way to know a heading is restricted
    # until the destination has rejected it).
    specs = [("dest_accept", n_per_slice), ("dest_hs_restricted", n_per_slice)]
    for slice_name, count in specs:
        for i in range(count):
            payload = _gen(slice_name, i, rng)
            adj = oracle.adjudicate(payload, lane=LANE_IN_US, error_type=NormalizedErrorType.UNKNOWN)
            cases.append(_Case(f"{prefix}-{slice_name}-{i:02d}", slice_name, payload, adj.accepted))
    return cases


def _interleave(adjs: list[Adjudication]) -> list[Adjudication]:
    """Round-robin accepted/rejected so every prefix of the stream is balanced.

    Models a realistic operational stream (a mix of outcomes over time) and keeps
    the learning curve monotonic: each step strengthens the per-heading evidence
    without swinging the accept/reject ratio among a case's nearest neighbours.
    """
    accepts = [a for a in adjs if a.accepted]
    rejects = [a for a in adjs if not a.accepted]
    out: list[Adjudication] = []
    for acc, rej in zip(accepts, rejects, strict=False):
        out.extend((acc, rej))
    out.extend(accepts[len(rejects):])
    out.extend(rejects[len(accepts):])
    return out


def _adjudication_of(case: _Case) -> Adjudication:
    """The training signal for one case (its real destination outcome)."""
    return Adjudication(
        memory_key=f"judge-eval|{case.slice}",
        error_type=NormalizedErrorType.UNKNOWN,
        accepted=case.oracle_accepted,
        source=get_oracle().adjudicate(case.payload, lane=LANE_IN_US).source,
        detail=f"{case.slice} destination outcome",
        features=case.features,
    )


def _gate_accepts(case: _Case, judge: LearnedJudge) -> tuple[bool, str]:
    """The gate's auto-clear decision: carrier-clean AND not learned-vetoed.

    Mirrors the production gate: the learned judge can only *tighten*, so an
    empty/cold store leaves the carrier-clean decision untouched.
    """
    if policy_lint(case.payload) is not None:
        return False, "carrier policy lint failed"
    verdict = judge.assess(case.features, NormalizedErrorType.UNKNOWN)
    if verdict.is_veto:
        return False, verdict.basis
    return True, verdict.basis or "no contrary precedent"


def _measure(cases: list[_Case], store: AdjudicationStore) -> tuple[dict, list[JudgeCaseResult]]:
    """Score the gate against the oracle. Positive class = oracle REJECTS."""
    judge = LearnedJudge(store=store)
    tp = fp = fn = tn = 0
    results: list[JudgeCaseResult] = []
    for case in cases:
        judge_accepts, basis = _gate_accepts(case, judge)
        oracle_accepts = case.oracle_accepted
        correct = judge_accepts == oracle_accepts
        false_auto_clear = judge_accepts and not oracle_accepts
        if not oracle_accepts and not judge_accepts:
            tp += 1
        elif oracle_accepts and not judge_accepts:
            fp += 1
        elif not oracle_accepts and judge_accepts:
            fn += 1
        else:
            tn += 1
        results.append(
            JudgeCaseResult(
                case_id=case.case_id,
                slice=case.slice,
                oracle_accepted=oracle_accepts,
                judge_accepted=judge_accepts,
                learned_vote="veto" if not judge_accepts and policy_lint(case.payload) is None else ("accept" if judge_accepts else "n/a"),
                correct=correct,
                false_auto_clear=false_auto_clear,
            )
        )
    total = len(cases)
    rejects = tp + fn
    metrics = {
        "accuracy": round((tp + tn) / total, 4) if total else 0.0,
        "precision": round(tp / (tp + fp), 4) if (tp + fp) else 0.0,
        "recall": round(tp / rejects, 4) if rejects else 0.0,
        "false_auto_clear_rate": round(fn / total, 4) if total else 0.0,
    }
    return metrics, results


def _learning_curve(
    test_cases: list[_Case], train_adjs: list[Adjudication], steps: int = 4
) -> list[LearningCurvePoint]:
    """Re-measure as progressively more adjudicated experience is added."""
    n = len(train_adjs)
    # Cumulative experience sizes from cold (0) to fully taught (n).
    sizes = sorted({round(n * s / steps) for s in range(steps + 1)})
    curve: list[LearningCurvePoint] = []
    for size in sizes:
        store = AdjudicationStore()
        for adj in train_adjs[:size]:
            store.add(adj)
        metrics, _ = _measure(test_cases, store)
        curve.append(
            LearningCurvePoint(
                n_adjudications=size,
                accuracy=metrics["accuracy"],
                false_auto_clear_rate=metrics["false_auto_clear_rate"],
                recall_on_rejects=metrics["recall"],
            )
        )
    return curve


def run_judge_eval(
    n_test_per_slice: int = 8,
    n_train_per_slice: int = 12,
    seed: int = 11,
    *,
    register_phoenix: bool | None = None,
    phoenix_client=None,  # noqa: ANN001 — test seam for the Phoenix client
) -> JudgeEvalReport:
    """Evaluate the judge against the independent oracle, with a learning curve."""
    oracle = get_oracle()
    test_cases = _build_cases("test", n_test_per_slice, seed, oracle)
    # Disjoint training pool (different rng stream, same destination patterns).
    train_cases = _build_cases("train", n_train_per_slice, seed + 1000, oracle)
    train_adjs = _interleave([_adjudication_of(c) for c in train_cases])

    # Headline metrics use the fully-taught judge.
    full_store = AdjudicationStore()
    for adj in train_adjs:
        full_store.add(adj)
    metrics, results = _measure(test_cases, full_store)

    curve = _learning_curve(test_cases, train_adjs)
    cold = curve[0].accuracy if curve else metrics["accuracy"]
    judge_source = "llm" if (settings.learned_judge_enabled and _llm_live()) else "knn"

    report = JudgeEvalReport(
        total=len(test_cases),
        accuracy=metrics["accuracy"],
        precision=metrics["precision"],
        recall=metrics["recall"],
        false_auto_clear_rate=metrics["false_auto_clear_rate"],
        judge_source=judge_source,
        learning_curve=curve,
        improvement=round(metrics["accuracy"] - cold, 4),
        cases=results,
    )

    registered = _register_phoenix_judge_eval(
        test_cases, full_store, report, client=phoenix_client, force=register_phoenix
    )
    if registered is not None:
        report.experiment_id, report.experiment_dataset_id = registered
        report.experiment_live = True

    logger.info(
        "judge_eval.complete",
        total=report.total,
        accuracy=report.accuracy,
        false_auto_clear_rate=report.false_auto_clear_rate,
        improvement=report.improvement,
        judge_source=report.judge_source,
    )
    return report


def _llm_live() -> bool:
    from clearport import llm

    return llm.is_live()


# ── Phoenix experiment (a REAL task that runs the judge; no label echo) ───────
def _experiment_id_of(ran) -> str | None:  # noqa: ANN001
    if isinstance(ran, dict):
        return ran.get("experiment_id") or ran.get("id")
    return getattr(ran, "experiment_id", None) or getattr(ran, "id", None)


def _dataset_id_of(dataset) -> str | None:  # noqa: ANN001
    if isinstance(dataset, dict):
        return dataset.get("id") or dataset.get("dataset_id")
    return getattr(dataset, "id", None) or getattr(dataset, "dataset_id", None)


def _register_phoenix_judge_eval(
    test_cases: list[_Case],
    store: AdjudicationStore,
    report: JudgeEvalReport,
    client=None,  # noqa: ANN001 — phoenix.client.Client, injected in tests
    force: bool | None = None,
) -> tuple[str, str | None] | None:
    """Upload the judge-eval as a real Phoenix experiment (opt-in).

    Unlike a label-echo experiment, the ``task`` here *runs the learned judge* on
    each declaration and the evaluators score its decision against the independent
    oracle label folded into the example — so "the judge agrees with truth" and
    "no false auto-clear" are genuinely computed in Phoenix.
    """
    enabled = force if force is not None else (
        (settings.clearport_phoenix_experiments or "off").lower() == "on"
    )
    if not enabled or not test_cases:
        return None
    try:
        import contextlib
        import io

        if client is None:
            from phoenix.client import Client

            client = Client(base_url=settings.phoenix_host, api_key=settings.phoenix_api_key)

        judge = LearnedJudge(store=store)
        inputs = [
            {
                "case_id": c.case_id,
                "slice": c.slice,
                "features": c.features,
                "oracle_accepted": c.oracle_accepted,
                "payload": c.payload.model_dump(mode="json"),
            }
            for c in test_cases
        ]
        outputs = [{"oracle_accepted": c.oracle_accepted} for c in test_cases]
        metadata = [{"slice": c.slice, "case_id": c.case_id} for c in test_cases]
        dataset_name = f"clearport-judge-eval::{new_id('judge')}"

        def task(input):  # noqa: ANN001, ANN202 — bound to example["input"]
            payload = CustomsPayload.model_validate(input["payload"])
            case = _Case(input.get("case_id", "?"), input.get("slice", "?"), payload, bool(input.get("oracle_accepted")))
            judge_accepts, basis = _gate_accepts(case, judge)
            return {"judge_accepted": judge_accepts, "basis": basis}

        def agrees_with_oracle(output, input) -> float:  # noqa: ANN001
            return 1.0 if bool((output or {}).get("judge_accepted")) == bool((input or {}).get("oracle_accepted")) else 0.0

        def no_false_auto_clear(output, input) -> float:  # noqa: ANN001
            judged = bool((output or {}).get("judge_accepted"))
            oracle_ok = bool((input or {}).get("oracle_accepted"))
            return 0.0 if (judged and not oracle_ok) else 1.0

        with contextlib.redirect_stdout(io.StringIO()):
            dataset = client.datasets.create_dataset(
                name=dataset_name, inputs=inputs, outputs=outputs, metadata=metadata
            )
            ran = client.experiments.run_experiment(
                dataset=dataset,
                task=task,
                evaluators={
                    "agrees_with_oracle": agrees_with_oracle,
                    "no_false_auto_clear": no_false_auto_clear,
                },
                experiment_name="clearport-judge-eval",
                experiment_metadata={
                    "accuracy": report.accuracy,
                    "false_auto_clear_rate": report.false_auto_clear_rate,
                    "improvement": report.improvement,
                },
                print_summary=False,
            )
        exp_id = _experiment_id_of(ran)
        if exp_id:
            logger.info("judge_eval.phoenix_registered", experiment_id=exp_id)
            return exp_id, _dataset_id_of(dataset)
        return None
    except Exception as exc:  # noqa: BLE001 — never let telemetry break the eval
        logger.warning("judge_eval.phoenix_failed", error=str(exc))
        return None


def _print_report(report: JudgeEvalReport) -> None:  # pragma: no cover - CLI sugar
    print("\nClearPort — Judge-quality evaluation (judge vs independent oracle)")
    print("=" * 68)
    print(f"  cases               : {report.total}")
    print(f"  judge backend       : {report.judge_source}")
    print(f"  accuracy            : {report.accuracy:.2%}")
    print(f"  precision (catch)   : {report.precision:.2%}")
    print(f"  recall on rejects   : {report.recall:.2%}")
    print(f"  false-auto-clear    : {report.false_auto_clear_rate:.2%}")
    print(f"  improvement (cold→taught): +{report.improvement:.2%}")
    print("\n  Learning curve (experience → quality):")
    print("   n_adj   accuracy   false-auto-clear   recall-on-rejects")
    for p in report.learning_curve:
        print(f"   {p.n_adjudications:>5}   {p.accuracy:>7.2%}   {p.false_auto_clear_rate:>15.2%}   {p.recall_on_rejects:>16.2%}")
    if report.experiment_live:
        print(f"\n  Phoenix experiment: {report.experiment_id}")
    print("")


def main() -> None:  # pragma: no cover - console entry point
    import logging

    import structlog as _structlog

    # Quiet the per-adjudication INFO stream so the report table is readable.
    _structlog.configure(
        wrapper_class=_structlog.make_filtering_bound_logger(logging.WARNING),
        processors=[_structlog.processors.JSONRenderer()],
    )
    report = run_judge_eval()
    _print_report(report)


if __name__ == "__main__":  # pragma: no cover
    main()
