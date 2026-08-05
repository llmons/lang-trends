# Lang Trends

Programming languages ranked by **new GitHub repositories with >100 stars** created in the past year. Data is refreshed daily and displayed as a static site.

## How it works

```
GitHub Search API
      ↓
Python (httpx) — queries 31 languages daily
      ↓
data/YYYY-MM-DD.json — one file per day, 10-day rolling window
      ↓
Astro — reads latest JSON at build time → static HTML
      ↓
GitHub Pages
```

- **Frontend** — Astro + Tailwind CSS v4, fully static, no client-side JS
- **Data pipeline** — Python script queries the GitHub Search API with `language:X stars:>100 created:>YYYY-MM-DD`
- **Automation** — GitHub Actions runs the fetch script daily, commits new data, and redeploys the site

## Quick start

```bash
# Install frontend dependencies
bun install

# Install Python dependencies
uv sync

# Start Astro dev server
bun run dev

# Run data collection (unauthenticated — 6s between requests, ~3 min total)
uv run python scripts/fetch_trends.py

# Build static site
bun run build
```

## Project structure

```
├── .github/workflows/
│   ├── fetch-data.yml       # Daily cron + manual trigger — runs Python, commits data
│   └── deploy.yml           # Push to main — builds Astro, deploys to GitHub Pages
├── scripts/
│   └── fetch_trends.py      # Query GitHub Search API, write JSON, cleanup old files
├── data/                    # Daily JSON files (Python writes here)
├── src/
│   ├── components/          # RankingTable.astro
│   ├── layouts/             # BaseLayout.astro
│   ├── lib/                 # Data loading (data.ts)
│   ├── pages/               # index.astro
│   └── styles/              # Global CSS + Tailwind tokens
├── test/
│   └── test_fetch_trends.py # Python pytest suite
├── pyproject.toml           # Python: uv + httpx + ruff + pytest
└── package.json             # Frontend: Astro + Tailwind CSS v4
```

## Data format

Each daily file (`data/YYYY-MM-DD.json`):

```json
{
  "date": "2026-08-05",
  "generated_at": "2026-08-05T11:35:28Z",
  "total_repos": 24799,
  "languages": [
    { "rank": 1, "name": "Python", "count": 8517 },
    { "rank": 2, "name": "TypeScript", "count": 5193 }
  ]
}
```

## Languages tracked

JavaScript, TypeScript, Python, Java, Go, Rust, C, C++, C#, PHP, Ruby, Swift, Kotlin, Dart, Shell, HTML, CSS, Scala, Lua, Elixir, Clojure, Haskell, R, Julia, Zig, OCaml, Groovy, Objective-C, Perl, PowerShell, MATLAB
