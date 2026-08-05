"""
Tests for scripts.fetch_trends — the GitHub Search API data collection script.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.fetch_trends import (
    SLEEP_S,
    build_query,
    cleanup_old_files,
    fetch_language_counts,
    fmt,
    write_data_file,
)


# ── fmt ──────────────────────────────────────────────────────────────────────


def test_fmt_thousands():
    assert fmt(0) == "0"
    assert fmt(1) == "1"
    assert fmt(999) == "999"


def test_fmt_with_commas():
    assert fmt(1000) == "1,000"
    assert fmt(42100) == "42,100"
    assert fmt(245321) == "245,321"


# ── build_query ──────────────────────────────────────────────────────────────


def test_build_query_includes_language():
    q = build_query("Python")
    assert "language:Python" in q


def test_build_query_includes_stars_filter():
    q = build_query("Go")
    assert "stars:>100" in q


def test_build_query_includes_created_date():
    q = build_query("Rust")
    # Should contain a YYYY-MM-DD date
    assert re.search(r"created:>\d{4}-\d{2}-\d{2}", q)


# ── fetch_language_counts ────────────────────────────────────────────────────


def make_mock_response(total_count: int) -> MagicMock:
    """Create a mock httpx response with a given total_count."""
    mock = MagicMock()
    mock.raise_for_status.return_value = None
    mock.json.return_value = {"total_count": total_count}
    return mock


def test_fetch_language_counts_returns_correct_length(monkeypatch):
    """Should return one entry per language, each with rank/name/count."""
    # Use a tiny language list to keep the test fast
    monkeypatch.setattr("scripts.fetch_trends.LANGUAGES", ["Python", "Rust"])
    monkeypatch.setattr("scripts.fetch_trends.SLEEP_S", 0)

    mock_resp = make_mock_response(8517)

    with patch("scripts.fetch_trends.httpx.get", return_value=mock_resp) as mock_get:
        results = fetch_language_counts()

    assert len(results) == 2
    assert mock_get.call_count == 2


def test_fetch_language_counts_assigns_ranks_sorted_by_count(monkeypatch):
    """Highest count gets rank 1."""
    monkeypatch.setattr("scripts.fetch_trends.LANGUAGES", ["A", "B", "C"])
    monkeypatch.setattr("scripts.fetch_trends.SLEEP_S", 0)

    # Return different counts for each call
    mock_a = make_mock_response(100)
    mock_b = make_mock_response(500)
    mock_c = make_mock_response(300)

    with patch("scripts.fetch_trends.httpx.get", side_effect=[mock_a, mock_b, mock_c]):
        results = fetch_language_counts()

    # Sorted by count desc: B(500) rank 1, C(300) rank 2, A(100) rank 3
    assert results[0] == {"name": "B", "count": 500, "rank": 1}
    assert results[1] == {"name": "C", "count": 300, "rank": 2}
    assert results[2] == {"name": "A", "count": 100, "rank": 3}


def test_fetch_language_counts_tiebreak_alphabetical(monkeypatch):
    """Equal counts sort alphabetically by name."""
    monkeypatch.setattr("scripts.fetch_trends.LANGUAGES", ["Zig", "Ada"])
    monkeypatch.setattr("scripts.fetch_trends.SLEEP_S", 0)

    mock = make_mock_response(50)

    with patch("scripts.fetch_trends.httpx.get", return_value=mock):
        results = fetch_language_counts()

    assert results[0]["name"] == "Ada"
    assert results[1]["name"] == "Zig"
    # Both rank 1 and 2 (tied count, alphabetical)
    assert results[0]["rank"] == 1
    assert results[1]["rank"] == 2


def test_fetch_language_counts_handles_http_error(monkeypatch):
    """HTTP errors set count to 0, and the language still appears."""
    monkeypatch.setattr("scripts.fetch_trends.LANGUAGES", ["Python"])
    monkeypatch.setattr("scripts.fetch_trends.SLEEP_S", 0)

    import httpx

    error_resp = MagicMock()
    error_resp.status_code = 422
    error_exc = httpx.HTTPStatusError("bad", request=MagicMock(), response=error_resp)

    with patch("scripts.fetch_trends.httpx.get", side_effect=error_exc):
        results = fetch_language_counts()

    assert results[0]["count"] == 0
    assert results[0]["rank"] == 1


def test_fetch_language_counts_handles_403_with_retry(monkeypatch):
    """403 triggers a retry after 60s; if retry succeeds, use that count."""
    monkeypatch.setattr("scripts.fetch_trends.LANGUAGES", ["Python"])
    monkeypatch.setattr("scripts.fetch_trends.SLEEP_S", 0)

    import httpx

    error_resp = MagicMock()
    error_resp.status_code = 403
    error_exc = httpx.HTTPStatusError("rate limited", request=MagicMock(), response=error_resp)
    success_mock = make_mock_response(8517)

    with patch("scripts.fetch_trends.httpx.get", side_effect=[error_exc, success_mock]):
        with patch("scripts.fetch_trends.time.sleep", return_value=None) as mock_sleep:
            results = fetch_language_counts()

    # Should have slept 60s for the retry
    mock_sleep.assert_called_once_with(60)
    assert results[0]["count"] == 8517


def test_fetch_language_counts_handles_request_error(monkeypatch):
    """Network errors set count to 0."""
    monkeypatch.setattr("scripts.fetch_trends.LANGUAGES", ["Python"])
    monkeypatch.setattr("scripts.fetch_trends.SLEEP_S", 0)

    import httpx

    with patch("scripts.fetch_trends.httpx.get", side_effect=httpx.RequestError("timeout")):
        results = fetch_language_counts()

    assert results[0]["count"] == 0


# ── write_data_file ──────────────────────────────────────────────────────────


def test_write_data_file_creates_json(tmp_path, monkeypatch):
    """Should write a JSON file with the correct shape to the data dir."""
    monkeypatch.setattr("scripts.fetch_trends.DATA_DIR", tmp_path)

    languages = [
        {"name": "Python", "count": 100, "rank": 1},
        {"name": "Rust", "count": 50, "rank": 2},
    ]
    filepath = write_data_file(languages)

    assert filepath.exists()
    data = json.loads(filepath.read_text())
    assert data["total_repos"] == 150
    assert data["languages"] == languages
    assert "date" in data
    assert "generated_at" in data
    # filename matches date
    assert filepath.name == f"{data['date']}.json"


def test_write_data_file_total_repos_summed_correctly(tmp_path, monkeypatch):
    """total_repos should be the sum of all language counts."""
    monkeypatch.setattr("scripts.fetch_trends.DATA_DIR", tmp_path)

    languages = [
        {"name": "A", "count": 10, "rank": 1},
        {"name": "B", "count": 20, "rank": 2},
        {"name": "C", "count": 30, "rank": 3},
    ]
    write_data_file(languages)

    # Find the file we just wrote
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert data["total_repos"] == 60


# ── cleanup_old_files ────────────────────────────────────────────────────────


def test_cleanup_deletes_files_beyond_limit(tmp_path, monkeypatch):
    """Should keep only MAX_DATA_FILES files, deleting the oldest."""
    monkeypatch.setattr("scripts.fetch_trends.DATA_DIR", tmp_path)
    monkeypatch.setattr("scripts.fetch_trends.MAX_DATA_FILES", 3)

    # Create 5 daily files
    dates = ["2026-08-01", "2026-08-02", "2026-08-03", "2026-08-04", "2026-08-05"]
    for d in dates:
        (tmp_path / f"{d}.json").write_text("{}")

    deleted = cleanup_old_files()

    assert len(deleted) == 2
    # Oldest two should be deleted
    assert {p.name for p in deleted} == {"2026-08-01.json", "2026-08-02.json"}
    # Newest three should remain
    remaining = sorted(f.name for f in tmp_path.glob("*.json"))
    assert remaining == ["2026-08-03.json", "2026-08-04.json", "2026-08-05.json"]


def test_cleanup_does_nothing_when_under_limit(tmp_path, monkeypatch):
    """No files deleted when count ≤ MAX_DATA_FILES."""
    monkeypatch.setattr("scripts.fetch_trends.DATA_DIR", tmp_path)
    monkeypatch.setattr("scripts.fetch_trends.MAX_DATA_FILES", 5)

    for d in ["2026-08-03", "2026-08-04"]:
        (tmp_path / f"{d}.json").write_text("{}")

    deleted = cleanup_old_files()
    assert len(deleted) == 0
    assert len(list(tmp_path.glob("*.json"))) == 2


def test_cleanup_handles_empty_dir(tmp_path, monkeypatch):
    """Empty data dir should not crash."""
    monkeypatch.setattr("scripts.fetch_trends.DATA_DIR", tmp_path)

    deleted = cleanup_old_files()
    assert deleted == []


def test_cleanup_handles_missing_dir(monkeypatch):
    """Non-existent dir should not crash."""
    monkeypatch.setattr("scripts.fetch_trends.DATA_DIR", Path("/no/such/dir"))

    deleted = cleanup_old_files()
    assert deleted == []


def test_cleanup_ignores_non_json_files(tmp_path, monkeypatch):
    """Only .json files with date-format names count toward the limit."""
    monkeypatch.setattr("scripts.fetch_trends.DATA_DIR", tmp_path)
    monkeypatch.setattr("scripts.fetch_trends.MAX_DATA_FILES", 1)

    (tmp_path / "2026-08-01.json").write_text("{}")
    (tmp_path / "2026-08-02.json").write_text("{}")
    (tmp_path / "notes.txt").write_text("hello")
    (tmp_path / "other.json").write_text("{}")  # not a date-format name

    deleted = cleanup_old_files()

    # Only 1 date-named JSON will be kept; 1 deleted
    assert len(deleted) == 1
    # The non-date JSON and txt file should be untouched
    assert (tmp_path / "notes.txt").exists()
    assert (tmp_path / "other.json").exists()
