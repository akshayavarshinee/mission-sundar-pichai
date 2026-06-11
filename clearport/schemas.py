"""ClearPort data contracts.

Every phase passes these pydantic models around. They are the single source of
truth for the shape of a rejection, a diagnosis, a patch, an eval verdict, a
risk decision, an outcome, and a distilled lesson. Keep this module free of
heavy imports (no EasyPost / Phoenix / Vertex) so it can be imported anywhere,
including pure unit tests.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ── helpers ──────────────────────────────────────────────────────────────────
def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ── enumerations (mirror EasyPost CustomsInfo semantics where relevant) ──────
class Source(str, Enum):
    """Which validation surface actually produced a rejection.

    Provenance is load-bearing for trust: we never let a rejection caught by our
    own rules masquerade as a carrier rejection.

    * ``EASYPOST`` — a real carrier rejection from the EasyPost API (CustomsInfo
      or Shipment creation failed).
    * ``HTS`` — the declared HS code failed validation against the external USITC
      Harmonized Tariff Schedule.
    * ``COMPLIANCE`` — ClearPort's own compliance rules engine caught a violation
      the carrier accepted (e.g. NOEEI at/above the FTR §30.37 $2,500 threshold)
      or the offline equivalent of a carrier rule.
    * ``OVERLAY`` — the destination regional rule overlay (drift surface).
    """

    EASYPOST = "easypost"
    HTS = "hts"
    COMPLIANCE = "compliance"
    OVERLAY = "overlay"

    @property
    def label(self) -> str:
        """Human-readable surface name for the UI's 'caught by' provenance."""
        return {
            Source.EASYPOST: "EasyPost carrier API",
            Source.HTS: "USITC HTS tariff schedule",
            Source.COMPLIANCE: "ClearPort Compliance Engine",
            Source.OVERLAY: "Destination rule overlay",
        }[self]


class ContentsType(str, Enum):
    MERCHANDISE = "merchandise"
    GIFT = "gift"
    DOCUMENTS = "documents"
    SAMPLE = "sample"
    RETURN_MERCHANDISE = "return_merchandise"
    OTHER = "other"


class RestrictionType(str, Enum):
    NONE = "none"
    OTHER = "other"
    QUARANTINE = "quarantine"
    SANITARY_PHYTOSANITARY_INSPECTION = "sanitary_phytosanitary_inspection"


class NormalizedErrorType(str, Enum):
    """Carrier/overlay errors normalized to a stable internal vocabulary."""

    HS_INVALID = "HS_INVALID"
    EEI_THRESHOLD_MISMATCH = "EEI_THRESHOLD_MISMATCH"
    RESTRICTION_COMMENTS_MISSING = "RESTRICTION_COMMENTS_MISSING"
    SIGNER_MISSING = "SIGNER_MISSING"
    CONTENTS_EXPLANATION_MISSING = "CONTENTS_EXPLANATION_MISSING"
    ZERO_VALUE = "ZERO_VALUE"
    OVERLAY_SCHEMA_DRIFT = "OVERLAY_SCHEMA_DRIFT"
    UNKNOWN = "UNKNOWN"


class Decision(str, Enum):
    AUTO = "AUTO"
    HUMAN = "HUMAN"


class ActionType(str, Enum):
    AUTO_BOUGHT = "AUTO_BOUGHT"
    HUMAN_APPROVED = "HUMAN_APPROVED"
    HUMAN_REJECTED = "HUMAN_REJECTED"
    HUMAN_CORRECTED = "HUMAN_CORRECTED"
    PENDING = "PENDING"


class CarrierResult(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    PENDING = "PENDING"


# ── core value objects ───────────────────────────────────────────────────────
class Lane(BaseModel):
    """A trade lane, ISO-3166 alpha-2 country codes (e.g. IN -> US)."""

    model_config = ConfigDict(frozen=True)

    origin: str
    dest: str

    def __str__(self) -> str:  # noqa: D105
        return f"{self.origin}->{self.dest}"


class Address(BaseModel):
    name: str
    street1: str
    city: str
    state: str | None = None
    zip: str | None = None
    country: str
    phone: str | None = None
    email: str | None = None


class ParcelSpec(BaseModel):
    """Physical parcel dimensions for an EasyPost Shipment."""

    weight_oz: float = Field(gt=0)
    length_in: float | None = None
    width_in: float | None = None
    height_in: float | None = None


class CustomsItemSpec(BaseModel):
    """One line on a customs declaration (maps to EasyPost CustomsItem)."""

    description: str
    quantity: int = Field(ge=0)
    # total line value in `currency` (EasyPost treats `value` as line total)
    value: float = Field(ge=0)
    weight_oz: float = Field(ge=0)
    origin_country: str
    hs_tariff_number: str | None = None
    currency: str = "USD"

    @property
    def hs_chapter(self) -> str:
        digits = "".join(c for c in (self.hs_tariff_number or "") if c.isdigit())
        return digits[:2] if len(digits) >= 2 else "??"


class CustomsPayload(BaseModel):
    """Our *mutable* representation of an EasyPost CustomsInfo.

    EasyPost CustomsInfo objects are immutable once created, so "patching" means
    building a corrected ``CustomsPayload`` and re-creating the CustomsInfo. This
    model is what the Patch Engine rewrites.
    """

    contents_type: ContentsType
    customs_certify: bool = True
    customs_signer: str | None = None
    contents_explanation: str | None = None
    restriction_type: RestrictionType = RestrictionType.NONE
    restriction_comments: str | None = None
    # EEI: e.g. "NOEEI 30.37(a)" (under-threshold) or an AES ITN for >= $2,500.
    eel_pfc: str | None = "NOEEI 30.37(a)"
    non_delivery_option: str = "return"
    items: list[CustomsItemSpec]

    @property
    def total_value(self) -> float:
        return round(sum(i.value for i in self.items), 2)

    @property
    def primary_hs_chapter(self) -> str:
        return self.items[0].hs_chapter if self.items else "??"

    def model_copy_deep(self) -> CustomsPayload:
        return self.model_copy(deep=True)


class RawError(BaseModel):
    """The carrier/overlay error exactly as received (pre-normalization)."""

    code: str | None = None
    message: str
    field: str | None = None


class MemoryKey(BaseModel):
    """Granularity of memory: {lane + HS-chapter + error-type}."""

    model_config = ConfigDict(frozen=True)

    lane: str
    hs_chapter: str
    error_type: NormalizedErrorType

    def as_str(self) -> str:
        return f"{self.lane}|hs{self.hs_chapter}|{self.error_type.value}"


# ── the loop's moving documents ──────────────────────────────────────────────
class RejectionEvent(BaseModel):
    """Trace root for one recovery loop."""

    id: str = Field(default_factory=lambda: new_id("rej"))
    created_at: datetime = Field(default_factory=utcnow)
    source: Source
    lane: Lane
    persona: str
    payload: CustomsPayload
    raw_error: RawError
    normalized_error_type: NormalizedErrorType = NormalizedErrorType.UNKNOWN
    seed_id: str | None = None  # which seed produced this (demo provenance)
    # shipping context (so the Executor can resubmit/buy and the Patch Engine
    # can fill a signer); optional so a bare rejection is still valid.
    shipper_name: str | None = None
    from_address: Address | None = None
    to_address: Address | None = None
    parcel: ParcelSpec | None = None

    @property
    def customs_value(self) -> float:
        return self.payload.total_value

    @property
    def memory_key(self) -> MemoryKey:
        return MemoryKey(
            lane=str(self.lane),
            hs_chapter=self.payload.primary_hs_chapter,
            error_type=self.normalized_error_type,
        )


class LawCitation(BaseModel):
    source: str  # "HTS" | "CROSS" | "EEI"
    ref: str
    text: str
    score: float = 0.0


class LessonRef(BaseModel):
    lesson_id: str
    key: str
    recommended_fix: str
    score: float = 0.0


class PrecedentExample(BaseModel):
    example_id: str
    summary: str
    accepted: bool


class Diagnosis(BaseModel):
    rejection_id: str
    root_cause: str
    affected_fields: list[str] = Field(default_factory=list)
    law_citations: list[LawCitation] = Field(default_factory=list)
    retrieved_lessons: list[LessonRef] = Field(default_factory=list)
    precedent_examples: list[PrecedentExample] = Field(default_factory=list)
    confidence: float = 0.0
    confidence_basis: str = ""


class FieldDiff(BaseModel):
    field: str
    before: str | None = None
    after: str | None = None


class PatchProposal(BaseModel):
    id: str = Field(default_factory=lambda: new_id("patch"))
    rejection_id: str
    patched_payload: CustomsPayload
    field_diff: list[FieldDiff] = Field(default_factory=list)
    rationale: str = ""
    tool_calls_used: list[str] = Field(default_factory=list)


class EvalRubric(BaseModel):
    structural_match: bool = False
    required_fields_ok: bool = False
    value_sanity: bool = False
    law_consistent: bool = False

    @property
    def all_pass(self) -> bool:
        return all(
            (self.structural_match, self.required_fields_ok, self.value_sanity, self.law_consistent)
        )


class EvalVerdict(BaseModel):
    id: str = Field(default_factory=lambda: new_id("eval"))
    patch_id: str
    judge_model: str
    passed: bool
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    confidence_basis: str = ""
    rubric: EvalRubric = Field(default_factory=EvalRubric)
    rationale: str = ""
    phoenix_annotation_id: str | None = None


class RiskAssessment(BaseModel):
    value_component: float
    danger_component: float
    confidence_component: float
    total_score: float
    hard_line_triggered: bool
    decision: Decision
    reasons: list[str] = Field(default_factory=list)


class TraceStep(BaseModel):
    """One step of the recovery loop, with its measured wall-clock duration.

    Mirrors the OpenTelemetry span emitted for the same step (recall, diagnose,
    patch, verify, decide, act, learn) so the dashboard can render a real trace
    waterfall without round-tripping to Phoenix.
    """

    name: str
    duration_ms: float
    detail: str = ""


class Outcome(BaseModel):
    id: str = Field(default_factory=lambda: new_id("out"))
    created_at: datetime = Field(default_factory=utcnow)
    patch_id: str
    rejection_id: str
    memory_key: str
    action: ActionType
    carrier_result: CarrierResult = CarrierResult.PENDING
    label_id: str | None = None
    recovery_seconds: float = 0.0
    demurrage_saved_usd: float = 0.0
    human_correction: CustomsPayload | None = None


class DistilledLesson(BaseModel):
    """Memory tier ③ — promoted only via a winning Arize experiment."""

    id: str = Field(default_factory=lambda: new_id("lesson"))
    key: MemoryKey
    pattern: str
    recommended_fix: str
    evidence_count: int = 0
    experiment_id: str | None = None
    baseline_score: float | None = None
    candidate_score: float | None = None
    promoted_at: datetime | None = None
    pass_rate: float = 1.0
