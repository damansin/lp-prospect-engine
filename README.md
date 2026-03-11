# LP Prospect Enrichment & Scoring Engine

An AI-powered pipeline that enriches LP prospect contacts with web research and scores them across 4 weighted dimensions to help PaceZero Capital Partners' fundraising team prioritize outreach.

## Architecture

```
CSV → Ingestion (org-level dedup) → Tavily Web Search → GPT-4o Analysis → Scoring → SQLite → Streamlit Dashboard
```

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Web Search | Tavily API | 3 targeted queries per org (investment profile, sustainability, emerging manager) |
| LLM Analysis | OpenAI GPT-4o | Structured scoring with org-type-aware prompts and rubrics |
| Database | SQLite + SQLAlchemy | Lightweight persistence with state management for resume |
| Dashboard | Streamlit + Plotly | Interactive BI layer with 6 pages for pipeline analysis |

## Quick Start

### 1. Install dependencies

```bash
cd LP_PROSPECT
pip install -r requirements.txt
```

### 2. Configure API keys

```bash
cp .env.example .env
```

Edit `.env` and add your keys:
- **OpenAI** — [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- **Tavily** — [tavily.com](https://tavily.com) (1,000 free searches/month)

### 3. Run the pipeline

```bash
# Full pipeline: ingest → enrich → score
python scripts/run_pipeline.py --csv challenge_contacts.csv

# Run phases independently (useful for debugging or re-scoring)
python scripts/run_pipeline.py --csv challenge_contacts.csv --ingest-only
python scripts/run_pipeline.py --enrich-only --batch-size 5
python scripts/run_pipeline.py --score-only
```

### 4. Launch the dashboard

```bash
streamlit run dashboard/app.py
```

Open **http://localhost:8501** in your browser.

## Scoring Model

| Dimension | Weight | Source | Description |
|-----------|--------|--------|-------------|
| Sector & Mandate Fit | 35% | AI (web search + GPT-4o) | Alignment with sustainability-focused private credit |
| Relationship Depth | 30% | CRM (CSV column, used as-is) | Pre-computed relationship strength |
| Halo & Strategic Value | 20% | AI (web search + GPT-4o) | Brand recognition, signaling value to attract other LPs |
| Emerging Manager Fit | 15% | AI (web search + GPT-4o) | Structural appetite for Fund I/II managers |

**Composite** = weighted sum → tier classification:

| Composite | Tier |
|-----------|------|
| >= 8.0 | PRIORITY CLOSE |
| >= 6.5 | STRONG FIT |
| >= 5.0 | MODERATE FIT |
| < 5.0 | WEAK FIT |

## Sample Output

The full scored results for all 100 contacts are in `sample_output.csv`. Top prospects:

| Rank | Contact | Organization | Score | Tier |
|------|---------|-------------|-------|------|
| 1 | Roman Torres Boscan | The Schmidt Family Foundation | 8.45 | PRIORITY CLOSE |
| 2 | Manuel Alvarez | Morgan Stanley AIP | 7.80 | STRONG FIT |
| 3 | Lorenzo Mendez | The Rockefeller Foundation | 7.65 | STRONG FIT |
| 4 | Alexander Gottlieb | Neuberger Berman | 7.50 | STRONG FIT |
| 5 | Minoti Dhanaraj | Pension Boards UCC | 7.20 | STRONG FIT |

**Tier distribution:** 1 Priority Close, 10 Strong Fit, 24 Moderate Fit, 64 Weak Fit

## CLI Flags

| Flag | Description |
|------|-------------|
| `--csv <path>` | Path to input CSV file |
| `--batch-size N` | Orgs per enrichment batch (default: 10) |
| `--skip-ingestion` | Skip CSV loading, use existing DB |
| `--skip-enrichment` | Skip web enrichment, use existing data |
| `--skip-scoring` | Skip scoring phase |
| `--ingest-only` | Only run CSV ingestion |
| `--enrich-only` | Only enrich pending orgs |
| `--score-only` | Only score enriched contacts |
| `--verbose` / `-v` | Debug logging |
| `--run-id <id>` | Custom run ID for cost tracking |

## Cost

~$0.04 per unique organization with GPT-4o (3 Tavily searches + 1 OpenAI analysis call).

| Scale | Unique Orgs | Estimated Cost |
|-------|-------------|----------------|
| 100 contacts | ~85 orgs | ~$4 |
| 1,000 contacts | ~800 orgs | ~$35 |
| 5,000 contacts | ~3,500 orgs | ~$140 |

## Key Design Decisions

See [WRITEUP.md](WRITEUP.md) for full details. Highlights:

- **Org-level deduplication** — Enrich once per organization, share across contacts. Saves ~15% API costs.
- **Two-phase enrichment** — Tavily searches first, then GPT-4o analyzes combined results in one structured call.
- **Org-type-aware prompting** — Different search strategies and LLM guidance for Foundations vs SFOs vs RIAs vs Pensions.
- **State management** — Pipeline can be interrupted and resumed; only processes pending orgs.
- **Calibration validation** — Post-scoring check against 4 anchor organizations to catch systematic drift.
- **Anomaly detection** — Flags logical inconsistencies (e.g., non-LP with high Sector Fit score).

## Project Structure

```
LP_PROSPECT/
├── src/
│   ├── config.py                  # Settings, API keys, weights, cost rates
│   ├── database.py                # SQLAlchemy engine and sessions
│   ├── models.py                  # ORM: Organization, Contact, Score, ApiCost
│   ├── cost_tracker.py            # Per-call API cost logging
│   ├── pipeline.py                # Main orchestrator (ingest → enrich → score)
│   ├── ingestion/
│   │   └── csv_loader.py          # CSV parsing, validation, org deduplication
│   ├── enrichment/
│   │   ├── web_search.py          # Tavily API — org-type-aware search queries
│   │   ├── llm_analyzer.py        # GPT-4o structured analysis with retry logic
│   │   ├── prompts.py             # All LLM prompt templates and scoring rubrics
│   │   └── enricher.py            # Enrichment orchestrator with batch processing
│   └── scoring/
│       ├── dimensions.py          # Composite formula, tiers, AUM parsing, check sizes
│       ├── calibration.py         # Anchor validation and anomaly detection
│       └── scorer.py              # Scoring orchestrator
├── dashboard/
│   └── app.py                     # Streamlit dashboard (6 pages)
├── scripts/
│   ├── run_pipeline.py            # CLI entry point
│   └── export_results.py          # Export scored data to CSV
├── data/                          # SQLite database (generated at runtime)
├── challenge_contacts.csv         # Input data
├── sample_output.csv              # Scored results for all 100 contacts
├── requirements.txt
├── .env.example
├── WRITEUP.md                     # Design decisions and tradeoffs
└── README.md
```
