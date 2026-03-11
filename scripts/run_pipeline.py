"""CLI entry point for the LP Prospect Enrichment & Scoring pipeline."""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline import Pipeline


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def main():
    parser = argparse.ArgumentParser(
        description="LP Prospect Enrichment & Scoring Engine"
    )
    parser.add_argument(
        "--csv", type=str, default=None,
        help="Path to the prospects CSV file"
    )
    parser.add_argument(
        "--skip-ingestion", action="store_true",
        help="Skip CSV ingestion (use existing DB data)"
    )
    parser.add_argument(
        "--skip-enrichment", action="store_true",
        help="Skip AI enrichment (use existing enrichment data)"
    )
    parser.add_argument(
        "--skip-scoring", action="store_true",
        help="Skip scoring (use existing scores)"
    )
    parser.add_argument(
        "--batch-size", type=int, default=10,
        help="Number of organizations per enrichment batch (default: 10)"
    )
    parser.add_argument(
        "--run-id", type=str, default=None,
        help="Custom run ID for cost tracking"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging"
    )
    parser.add_argument(
        "--ingest-only", action="store_true",
        help="Only run CSV ingestion, then exit"
    )
    parser.add_argument(
        "--enrich-only", action="store_true",
        help="Only run enrichment on pending orgs, then exit"
    )
    parser.add_argument(
        "--score-only", action="store_true",
        help="Only run scoring on enriched orgs, then exit"
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    pipeline = Pipeline(run_id=args.run_id)

    if args.ingest_only:
        if not args.csv:
            parser.error("--csv is required with --ingest-only")
        results = pipeline.ingest_only(args.csv)
        print(f"\nIngestion results: {results}")
        return

    if args.enrich_only:
        results = pipeline.enrich_only(batch_size=args.batch_size)
        print(f"\nEnrichment results: {results}")
        return

    if args.score_only:
        results = pipeline.score_only()
        print(f"\nScoring results: {results}")
        return

    results = pipeline.run(
        csv_path=args.csv,
        skip_ingestion=args.skip_ingestion,
        skip_enrichment=args.skip_enrichment,
        skip_scoring=args.skip_scoring,
        batch_size=args.batch_size,
    )

    print("\n" + "=" * 60)
    print("PIPELINE RESULTS")
    print("=" * 60)
    for key, value in results.items():
        if key == "cost_summary":
            print(f"\nCost Summary:")
            print(f"  Total Cost: ${value['total_cost']:.4f}")
            print(f"  API Calls:  {value['total_api_calls']}")
            print(f"  Tavily:     {value['tavily_calls']} calls")
            print(f"  OpenAI:     {value['openai_calls']} calls")
            print(f"  Tokens In:  {value['total_tokens_input']:,}")
            print(f"  Tokens Out: {value['total_tokens_output']:,}")
        else:
            print(f"\n{key}: {value}")
    print("=" * 60)


if __name__ == "__main__":
    main()
