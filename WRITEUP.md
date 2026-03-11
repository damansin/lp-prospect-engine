# Design Decisions & Tradeoffs

## Architecture

The system is a three-phase pipeline — **Ingestion → Enrichment → Scoring** — with a Streamlit dashboard for visualization. Each phase is independently runnable, so the team can re-score without re-enriching, or re-enrich a subset without re-ingesting.

**Org-level deduplication** is the core abstraction. The CSV has ~100 contacts across ~94 unique organizations. Since enrichment is about the *organization's* mandate, AUM, and sustainability focus — not the individual — we enrich once per org and share data across all contacts at that org. This cuts API costs by ~15% and ensures consistent scoring for colleagues at the same firm. Scoring remains per-contact because Relationship Depth (Dimension 2) varies by individual.

## Enrichment Strategy

We use a **two-phase enrichment** approach: Tavily handles web search (3 targeted queries per org), then GPT-4o analyzes the aggregated results in a single structured call. Separating search from analysis gives us better cost tracking, easier debugging, and the ability to swap search providers without touching scoring logic.

**Org-type-aware prompting** is critical. The same prompt doesn't work well across Foundation, SFO, and RIA org types. Foundations have public investment offices buried under mission-focused content. SFOs may or may not allocate externally. RIAs might be allocators or service providers. Both search queries and LLM prompts adapt based on org type to steer toward the right signals — for example, the Foundation prompt explicitly says "focus on investment activities, not philanthropic programs."

## Scoring & Calibration

Scores for Dimensions 1, 3, and 4 are produced by GPT-4o using detailed rubrics embedded in the prompt. Dimension 2 (Relationship Depth) is taken directly from the CRM data in the CSV. The composite score uses the specified weighted formula (35/30/20/15) and classifies into four tiers.

**Calibration anchors** (Rockefeller Foundation, PBUCC, Inherent Group, Meridian Capital) serve as regression tests. After every run, we compare outputs against expected scores and flag deviations > 2 points. **Anomaly detection** catches logical inconsistencies: a non-LP scoring high on Sector Fit, or a Foundation scoring below 4.

When the system cannot find sufficient public data, it signals this explicitly: score defaults to 4 with confidence="Low" and reasoning="Insufficient public data." This is enforced at three levels — the LLM prompt instruction, a response validator, and field-level defaults.

## Tradeoffs

- **GPT-4o over GPT-4o-mini**: Better scoring accuracy for nuanced LP vs GP distinctions. ~50x more expensive per token, but total cost is still <$4 for 100 contacts.
- **SQLite over Postgres**: Zero-config, portable, great for prototyping and review. Would migrate to Postgres for production concurrent access.
- **Synchronous over async pipeline**: Simpler code, easier debugging. Sufficient for ~100 orgs (~13 min runtime). Would add async concurrency for 1,000+ orgs.
- **Streamlit over React**: Fast to build, Python-native, interactive. Limited customization but sufficient for a fundraising team's internal tool.

## What I'd Improve With More Time

1. **Async enrichment** with semaphore-based concurrency for 10x throughput at scale.
2. **Multi-source enrichment** — PitchBook, Preqin, or Crunchbase APIs for higher-confidence AUM and allocation data.
3. **Human-in-the-loop review queue** for low-confidence scores before finalizing.
4. **Incremental re-enrichment** — detect stale data (>90 days) and selectively refresh.
5. **Export to CRM** — CSV/Excel export formatted for Salesforce or HubSpot import.
6. **Deterministic test suite** — mock API responses for unit testing scoring logic without live calls.
