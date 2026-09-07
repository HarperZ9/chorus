import json

from chorus.decision import build_decision, decision_from_paths


def _reference_rows():
    return [
        {
            "kind": "comment",
            "id": "kept",
            "ref": "workflow",
            "text": "fast install works well",
            "meta": {"like_count": 12, "source_url": "https://example.test/comments/kept"},
        },
        {
            "kind": "comment",
            "id": "changed",
            "ref": "workflow",
            "text": "login barrier is bad and slow",
            "meta": {"like_count": 4, "source_url": "https://example.test/comments/changed"},
        },
        {
            "kind": "comment",
            "id": "removed",
            "ref": "workflow",
            "text": "private payload should not leak",
            "meta": {"like_count": 2, "source_url": "https://example.test/comments/removed"},
        },
    ]


def _current_rows():
    return [
        {
            "kind": "comment",
            "id": "kept",
            "ref": "workflow",
            "text": "fast install works well",
            "meta": {"like_count": 12, "source_url": "https://example.test/comments/kept"},
        },
        {
            "kind": "comment",
            "id": "changed",
            "ref": "workflow",
            "text": "login barrier is bad and expensive",
            "meta": {"like_count": 4, "source_url": "https://example.test/comments/changed"},
        },
        {
            "kind": "comment",
            "id": "added",
            "ref": "workflow",
            "text": "sync workflows need durable memory migration",
            "meta": {"like_count": 8, "source_url": "https://example.test/comments/added"},
        },
    ]


def test_source_decision_reports_added_removed_and_changed_items_without_public_raw_text():
    result = build_decision(
        _current_rows(),
        _reference_rows(),
        task="Decide whether the gathered workflow evidence changed before release.",
    )

    assert result["ok"] is True
    assert result["status"] == "DRIFT"
    assert result["decision"] == "review_current_sources"
    assert result["changes"]["counts"] == {
        "added": 1,
        "removed": 1,
        "changed": 1,
        "unchanged": 1,
    }
    assert [row["id"] for row in result["changes"]["added"]] == ["added"]
    assert [row["id"] for row in result["changes"]["removed"]] == ["removed"]
    assert [row["id"] for row in result["changes"]["changed"]] == ["changed"]
    assert result["checks"]["current_digest_verified"] is True
    assert result["checks"]["reference_digest_verified"] is True

    public_text = json.dumps(result["public_projection"], ensure_ascii=False)
    assert "private payload should not leak" not in public_text
    assert "sync workflows need durable memory migration" not in public_text
    assert "https://example.test/comments/added" not in public_text
    assert result["public_projection"]["changes"]["counts"]["changed"] == 1


def test_public_projection_includes_source_url_only_when_explicitly_allowed():
    result = build_decision(
        [
            {
                "kind": "comment",
                "id": "same-id",
                "ref": "workflow",
                "text": "changed source",
                "meta": {
                    "like_count": 1,
                    "source_url": "https://example.test/comments/same-id",
                    "public_projection_url_allowed": True,
                },
            }
        ],
        [
            {
                "kind": "comment",
                "id": "same-id",
                "ref": "workflow",
                "text": "reference source",
                "meta": {"like_count": 1, "source_url": "https://example.test/comments/same-id"},
            }
        ],
        task="Project only explicitly allowlisted source URLs.",
    )

    public = result["public_projection"]["changes"]["changed"][0]
    assert public["current"]["source_url"] == "https://example.test/comments/same-id"
    assert "source_url" not in public["reference"]


def test_changed_text_is_drift_even_when_each_digest_receipt_verifies():
    result = build_decision(
        [
            {
                "kind": "comment",
                "id": "same-id",
                "ref": "workflow",
                "text": "the source now says the connector fails closed",
                "meta": {"like_count": 3},
            }
        ],
        [
            {
                "kind": "comment",
                "id": "same-id",
                "ref": "workflow",
                "text": "the source says the connector works",
                "meta": {"like_count": 3},
            }
        ],
        task="Detect altered source content.",
    )

    assert result["status"] == "DRIFT"
    assert result["changes"]["counts"] == {"added": 0, "removed": 0, "changed": 1, "unchanged": 0}
    assert result["checks"]["current_digest_verified"] is True
    assert result["checks"]["reference_digest_verified"] is True


def test_missing_current_path_is_a_typed_unverifiable_result(tmp_path):
    reference = tmp_path / "reference.json"
    reference.write_text(json.dumps(_reference_rows()), encoding="utf-8")

    result = decision_from_paths(
        str(tmp_path / "missing.json"),
        str(reference),
        task="Detect missing source failures.",
    )

    assert result["ok"] is False
    assert result["status"] == "UNVERIFIABLE"
    assert result["decision"] == "hold_for_source_repair"
    assert result["source_failures"][0]["code"] == "missing_current"
    assert result["source_counts"]["reference_rows"] == 3
    assert result["source_counts"]["reference_items"] == 3
