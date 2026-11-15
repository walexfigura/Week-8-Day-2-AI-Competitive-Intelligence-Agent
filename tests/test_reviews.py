"""Review datasets, duplicate detection, aspect aggregation, and the LLM annotator contract."""

from __future__ import annotations

import json

import pytest

from competitive_intelligence.analysis.sentiment import (
    ANNOTATION_SCHEMA,
    AnnotationError,
    aggregate,
    annotate_reviews_llm,
    find_duplicates,
    reference_annotations,
    sample_statement,
)
from competitive_intelligence.models import ReviewAnnotation

from .conftest import FakeResponse


def pt(services):
    meta, reviews = services.fixture_reviews.get("PT-RIDGE")
    return meta, reviews


def test_dataset_sizes(services):
    assert len(pt(services)[1]) == 21  # 20 unique + 1 syndicated duplicate
    assert len(services.fixture_reviews.get("SW-METRO")[1]) == 15
    assert len(services.fixture_reviews.get("TF-APEX")[1]) == 15


def test_review_ids_are_unique_and_fictional(services):
    for pid in ("PT-RIDGE", "SW-METRO", "TF-APEX"):
        meta, reviews = services.fixture_reviews.get(pid)
        assert "FICTIONAL" in meta["notice"]
        ids = [r.review_id for r in reviews]
        assert len(ids) == len(set(ids))
        assert all(".example" in r.source_ref for r in reviews)


def test_exactly_eight_unique_peaktrail_reviews_mention_lid_leaks(services):
    meta, reviews = pt(services)
    unique = [r for r in reviews if r.review_id not in find_duplicates(reviews)]
    ann = reference_annotations(services.fixture_reviews.reference_annotations("PT-RIDGE"), unique)
    agg = aggregate(reviews, ann, meta=meta)
    lid = next(t for t in agg["themes"] if (t["aspect"], t["sentiment"]) == ("lid_leak_resistance", "negative"))
    assert lid["review_count"] == 8 and lid["sample_size"] == 20
    assert lid["statement"] == "8 of the 20 reviews in our sample mention problems with lid leakage."
    assert "PT-R21" not in lid["review_ids"]
    assert lid["recurring"] is True


def test_statement_never_uses_percentages():
    s = sample_statement(8, 20, "lid_leak_resistance", "negative")
    assert "%" not in s and "customers" not in s
    assert sample_statement(1, 15, "shipping", "negative").startswith("1 of the 15 reviews in our sample mentions")


def test_duplicates(services):
    d = find_duplicates(pt(services)[1])
    assert d == {"PT-R21": {"duplicate_of": "PT-R04", "kind": "exact_duplicate"}}
    sw = find_duplicates(services.fixture_reviews.get("SW-METRO")[1])
    assert sw["SW-R08"]["kind"] == "near_duplicate"


def test_mixed_and_high_star_complaints(services):
    meta, reviews = pt(services)
    unique = [r for r in reviews if r.review_id not in find_duplicates(reviews)]
    agg = aggregate(reviews, reference_annotations(services.fixture_reviews.reference_annotations("PT-RIDGE"), unique), meta=meta)
    assert "PT-R01" in agg["reviews_with_mixed_sentiment"]
    assert "PT-R08" in agg["four_or_five_star_reviews_with_complaints"]
    assert set(agg["ambiguous_review_ids"]) == {"PT-R10", "PT-R18"}


def test_injection_review_flagged(services):
    meta, reviews = services.fixture_reviews.get("SW-METRO")
    unique = [r for r in reviews if r.review_id not in find_duplicates(reviews)]
    agg = aggregate(reviews, reference_annotations(services.fixture_reviews.reference_annotations("SW-METRO"), unique), meta=meta)
    assert agg["possible_prompt_injection_review_ids"] == ["SW-R12"]


def _fake_annotator(payload):
    class C:
        class responses:
            requests = []

            @staticmethod
            def create(**kwargs):
                C.responses.requests.append(kwargs)
                return FakeResponse(output=[], output_text=payload)

    return C


def test_llm_annotator_uses_strict_structured_outputs(services):
    meta, reviews = pt(services)
    unique = [r for r in reviews if r.review_id not in find_duplicates(reviews)]
    gold = reference_annotations(services.fixture_reviews.reference_annotations("PT-RIDGE"), unique)
    client = _fake_annotator(json.dumps({"annotations": [a.model_dump() for a in gold]}))
    out = annotate_reviews_llm(client, "test-model", unique)
    assert [a.review_id for a in out] == [r.review_id for r in unique]
    req = client.responses.requests[0]
    fmt = req["text"]["format"]
    assert fmt["type"] == "json_schema" and fmt["strict"] is True and fmt["schema"] is ANNOTATION_SCHEMA
    assert "<reviews>" in req["input"][0]["content"]  # reviews are delimited as data


def test_llm_annotator_rejects_bad_output(services):
    _, reviews = pt(services)
    with pytest.raises(AnnotationError):
        annotate_reviews_llm(_fake_annotator("not json"), "m", reviews[:2])
    partial = json.dumps({"annotations": [ReviewAnnotation(review_id=reviews[0].review_id, aspects=[]).model_dump()]})
    with pytest.raises(AnnotationError):
        annotate_reviews_llm(_fake_annotator(partial), "m", reviews[:2])
    bad_aspect = json.dumps({"annotations": [{"review_id": reviews[0].review_id, "aspects": [{"aspect": "vibes", "sentiment": "positive",
                                              "evidence_quote": ""}], "ambiguous": False, "possible_prompt_injection": False, "notes": None}]})
    with pytest.raises(AnnotationError):
        annotate_reviews_llm(_fake_annotator(bad_aspect), "m", reviews[:1])


def test_strict_schema_requires_every_property():
    def walk(schema):
        if schema.get("type") == "object":
            assert schema["additionalProperties"] is False
            assert set(schema["required"]) == set(schema["properties"])
            for v in schema["properties"].values():
                walk(v)
        if schema.get("type") == "array":
            walk(schema["items"])

    walk(ANNOTATION_SCHEMA)


def test_export_review_source_reads_csv(tmp_path, services):
    from competitive_intelligence.integrations.mock_sources import ExportReviewSource

    (tmp_path / "PT-RIDGE.csv").write_text(
        "review_id,review_date,rating,title,text,source_ref\nEX-1,2026-11-01,4,Nice,Keeps water cold.,export.csv\n", encoding="utf-8")
    meta, reviews = ExportReviewSource(tmp_path, services.watchlist).get("PT-RIDGE")
    assert reviews[0].review_id == "EX-1" and reviews[0].competitor_id == "peaktrail"
