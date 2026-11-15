"""Data models shared by tools, analysis, and reports.

Pydantic validates the fixture files when they load, so a typo in a JSON
snapshot (a price written as text, a bad timestamp, a 4-letter currency)
fails loudly instead of quietly producing a wrong finding.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Availability = Literal["in_stock", "out_of_stock", "preorder", "discontinued"]
Priority = Literal["high", "medium", "low", "insufficient_evidence"]
Confidence = Literal["high", "medium", "low"]
Sentiment = Literal["positive", "negative", "neutral", "mixed"]

ASPECTS: tuple[str, ...] = (
    "insulation",
    "lid_leak_resistance",
    "lid_usability",
    "durability",
    "design",
    "value",
    "weight",
    "size_fit",
    "cleaning",
    "shipping",
    "customer_service",
    "general",
)
ASPECT_CATEGORY: dict[str, str] = {
    **{a: "product_quality" for a in ASPECTS},
    "shipping": "fulfillment",
    "customer_service": "service",
    "general": "general",
}

SAFE_ID = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$"


class Promotion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    ends_at: str | None = None


class ProductSnapshot(BaseModel):
    """One normalized observation of one product page at one point in time."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    fictional: bool = True
    snapshot_id: str = Field(pattern=SAFE_ID)
    source_id: str = Field(pattern=SAFE_ID)
    competitor_id: str
    product_id: str = Field(pattern=SAFE_ID)
    product_name: str
    variant_id: str | None = None
    variant_label: str | None = None
    size_oz: float | None = None
    storefront: str = "US"
    observed_at: str
    current_price: float | None = Field(default=None, ge=0)
    list_price: float | None = Field(default=None, ge=0)
    currency: str | None = None
    promotion: Promotion | None = None
    availability: Availability | None = None
    features: list[str] = Field(default_factory=list)
    headline: str | None = None
    marketing_copy: str | None = None
    hidden_text: str | None = None
    source_url: str
    capture_method: str = "mock_fixture"
    fixture: str | None = None
    page_hash: str | None = None
    notes: str | None = None

    @field_validator("observed_at")
    @classmethod
    def _valid_timestamp(cls, value: str) -> str:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("observed_at must include a timezone (e.g. 2026-11-01T15:00:00Z)")
        return value

    @field_validator("currency")
    @classmethod
    def _valid_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if len(value) != 3 or not value.isalpha() or not value.isupper():
            raise ValueError("currency must be a 3-letter ISO code such as USD")
        return value

    @property
    def observed_datetime(self) -> datetime:
        return datetime.fromisoformat(self.observed_at.replace("Z", "+00:00"))

    def missing_fields(self) -> list[str]:
        missing = []
        for name in ("current_price", "currency", "availability", "variant_id"):
            if getattr(self, name) is None:
                missing.append(name)
        if not self.features:
            missing.append("features")
        return missing

    @property
    def is_complete(self) -> bool:
        return not self.missing_fields()


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: str = Field(pattern=SAFE_ID)
    competitor_id: str
    product_id: str
    variant_id: str | None = None
    review_date: str
    rating: int | None = Field(default=None, ge=1, le=5)
    title: str | None = None
    text: str
    reviewer: str | None = None
    verified_purchase: bool | None = None
    source_id: str
    source_ref: str


class AspectMention(BaseModel):
    model_config = ConfigDict(extra="forbid")
    aspect: str
    sentiment: Sentiment
    evidence_quote: str = ""

    @field_validator("aspect")
    @classmethod
    def _known_aspect(cls, value: str) -> str:
        if value not in ASPECTS:
            raise ValueError(f"unknown aspect {value!r}; expected one of {', '.join(ASPECTS)}")
        return value


class ReviewAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review_id: str
    aspects: list[AspectMention]
    ambiguous: bool = False
    possible_prompt_injection: bool = False
    notes: str | None = None


class EvidenceRef(BaseModel):
    snapshot_id: str
    source_id: str
    observed_at: str
    source_url: str


class ChangeEvent(BaseModel):
    event_id: str
    change_type: str
    field: str
    competitor_id: str
    product_id: str
    variant_id: str | None
    old_value: Any = None
    new_value: Any = None
    magnitude: dict[str, Any] | None = None
    caveats: list[str] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)


class ComparisonResult(BaseModel):
    product_id: str
    old_snapshot_id: str
    new_snapshot_id: str
    status: Literal["changes_detected", "no_meaningful_change", "not_comparable", "incomplete_data"]
    comparable: bool
    comparability_issues: list[str] = Field(default_factory=list)
    formatting_only: bool = False
    events: list[ChangeEvent] = Field(default_factory=list)
    unchanged_fields: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
