import json
from chorus.cli import main


def test_run_on_json_rows_prints_digest(tmp_path, capsys):
    rows = [
        {"kind": "comment", "id": "a", "ref": "v", "text": "great sound design",
         "meta": {"author": "x", "like_count": 20}},
        {"kind": "comment", "id": "b", "ref": "v", "text": "loved the sound design",
         "meta": {"author": "y", "like_count": 3}},
        {"kind": "comment", "id": "c", "ref": "v", "text": "the plot was bad",
         "meta": {"author": "z", "like_count": 9}},
    ]
    p = tmp_path / "items.json"
    p.write_text(json.dumps(rows), encoding="utf-8")

    assert main(["run", str(p), "--verify"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["responds_to"] == "v" and out["n_items"] == 3
    assert out["themes"] and "receipt" in out
    assert out["verified"] is True


def test_run_missing_path_is_error(capsys):
    assert main(["run", "does_not_exist.json"]) == 1
    assert "not found" in capsys.readouterr().err


def test_run_non_list_json_is_a_clean_error_not_a_traceback(tmp_path, capsys):
    p = tmp_path / "obj.json"
    p.write_text('{"kind": "comment"}', encoding="utf-8")   # a dict, not a list of rows
    assert main(["run", str(p)]) == 1
    assert "must be a list" in capsys.readouterr().err


def test_run_malformed_json_is_a_clean_error(tmp_path, capsys):
    p = tmp_path / "broken.json"
    p.write_text("{not valid json", encoding="utf-8")
    assert main(["run", str(p)]) == 1
    assert "could not read" in capsys.readouterr().err
