"""
Fetch programming language trends from the GitHub Search API.

Queries the number of new repositories (>100 stars, past year) per language,
writes the results to data/YYYY-MM-DD.json, and cleans up files older than 10 days.

Usage:
    uv run python scripts/fetch_trends.py
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

# ── Configuration ────────────────────────────────────────────────────────────

# Repositories created after this date (rolling 1-year window)
CUTOFF_DATE = (date.today() - timedelta(days=365)).isoformat()

# Where daily JSON files are stored (relative to repo root)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# How many daily files to keep
MAX_DATA_FILES = 10

# Languages to query (31 total)
LANGUAGES = [
    "JavaScript",
    "TypeScript",
    "Python",
    "Java",
    "Go",
    "Rust",
    "C",
    "C++",
    "C#",
    "PHP",
    "Ruby",
    "Swift",
    "Kotlin",
    "Dart",
    "Shell",
    "HTML",
    "CSS",
    "Scala",
    "Lua",
    "Elixir",
    "Clojure",
    "Haskell",
    "R",
    "Julia",
    "Zig",
    "OCaml",
    "Groovy",
    "Objective-C",
    "Perl",
    "PowerShell",
    "MATLAB",
]

# GitHub Search API endpoint
API_URL = "https://api.github.com/search/repositories"

# HTTP headers (unauthenticated)
HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "lang-trends/0.1.0",
}

# Seconds to sleep between requests (unauthenticated limit: 10 req/min)
SLEEP_S = 6.0


# ── Helpers ──────────────────────────────────────────────────────────────────


def build_query(language: str) -> str:
    """Build the GitHub search query for a language."""
    # e.g. "language:Python stars:>100 created:>2025-08-05"
    return f"language:{language} stars:>100 created:>{CUTOFF_DATE}"


def fmt(n: int) -> str:
    """Format a number with commas for logging."""
    return f"{n:,}"


# ── Core ─────────────────────────────────────────────────────────────────────


def fetch_language_counts() -> list[dict]:
    """
    Query the GitHub Search API for each language and return results sorted
    by count descending, each with a rank assigned.
    """
    results: list[dict] = []
    total = len(LANGUAGES)

    print(f"Querying {total} languages (cutoff: {CUTOFF_DATE})")
    print(f"Sleep between requests: {SLEEP_S}s\n")

    for i, lang in enumerate(LANGUAGES, start=1):
        query = build_query(lang)
        params = {"q": query, "per_page": 1}

        try:
            resp = httpx.get(
                API_URL,
                params=params,
                headers=HEADERS,
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            count = data.get("total_count", 0)

            print(f"  [{i:2d}/{total}] {lang:<15s} → {fmt(count)} repos")

        except httpx.HTTPStatusError as exc:
            # 403 usually means rate-limited; 422 means bad query
            print(
                f"  [{i:2d}/{total}] {lang:<15s} → ERROR {exc.response.status_code}",
                file=sys.stderr,
            )
            if exc.response.status_code == 403:
                print("    Rate limit hit — waiting 60s before retrying…", file=sys.stderr)
                time.sleep(60)
                try:
                    resp = httpx.get(
                        API_URL,
                        params=params,
                        headers=HEADERS,
                        timeout=30.0,
                    )
                    resp.raise_for_status()
                    count = resp.json().get("total_count", 0)
                    print(f"  [{i:2d}/{total}] {lang:<15s} → {fmt(count)} repos (retry ok)")
                except Exception:
                    print("    Retry also failed, setting count=0", file=sys.stderr)
                    count = 0
            else:
                count = 0

        except httpx.RequestError as exc:
            print(f"  [{i:2d}/{total}] {lang:<15s} → REQUEST ERROR: {exc}", file=sys.stderr)
            count = 0

        results.append({"name": lang, "count": count})

        # Rate-limit sleep (skip after the last request)
        if i < total:
            time.sleep(SLEEP_S)

    # Sort by count descending, then alphabetically for ties
    results.sort(key=lambda r: (-r["count"], r["name"]))

    # Assign ranks
    for idx, entry in enumerate(results):
        entry["rank"] = idx + 1

    return results


def write_data_file(languages: list[dict]) -> Path:
    """Write the daily JSON file and return its path."""
    today = date.today().isoformat()
    total_repos = sum(lang["count"] for lang in languages)
    now_utc = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    payload = {
        "date": today,
        "generated_at": now_utc,
        "total_repos": total_repos,
        "languages": languages,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    filepath = DATA_DIR / f"{today}.json"

    filepath.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {filepath} ({fmt(total_repos)} total repos across {len(languages)} languages)")

    return filepath


def cleanup_old_files() -> list[Path]:
    """Delete old data files beyond MAX_DATA_FILES. Returns list of deleted files."""
    if not DATA_DIR.is_dir():
        return []

    data_files = sorted(
        [f for f in DATA_DIR.iterdir() if f.suffix == ".json" and f.stem.count("-") == 2],
        key=lambda f: f.name,
    )

    deleted: list[Path] = []
    while len(data_files) > MAX_DATA_FILES:
        old = data_files.pop(0)  # oldest first
        old.unlink()
        deleted.append(old)
        print(f"Deleted old data file: {old.name}")

    return deleted


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    """Entry point — fetch data, write file, clean up old files."""
    print("=" * 60)
    print("  Lang Trends — Data Fetcher")
    print("=" * 60)
    print()

    languages = fetch_language_counts()
    filepath = write_data_file(languages)
    cleanup_old_files()

    print(f"\nDone — {filepath}")


if __name__ == "__main__":
    main()
