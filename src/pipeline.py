import logging
import uuid
from pathlib import Path
from src.database import init_db, get_session
from src.ingestion.csv_loader import load_csv, ingest_to_db
from src.enrichment.enricher import EnrichmentEngine
from src.scoring.scorer import ScoringEngine
from src.cost_tracker import CostTracker

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, run_id: str | None = None):
        self.run_id = run_id or str(uuid.uuid4())[:8]
        self.session = get_session()
        self.cost_tracker = CostTracker(self.session, self.run_id)

    def run(self, csv_path: str | None = None, skip_ingestion: bool = False,
            skip_enrichment: bool = False, skip_scoring: bool = False,
            batch_size: int = 10) -> dict:
        """Execute the full pipeline: ingest → enrich → score."""
        results = {"run_id": self.run_id}

        try:
            init_db()
            logger.info(f"=== Pipeline Run: {self.run_id} ===")

            if not skip_ingestion and csv_path:
                logger.info("--- Phase 1: CSV Ingestion ---")
                df = load_csv(csv_path)
                ingestion_stats = ingest_to_db(self.session, df)
                results["ingestion"] = ingestion_stats
                logger.info(f"Ingestion: {ingestion_stats}")

            if not skip_enrichment:
                logger.info("--- Phase 2: Enrichment ---")
                enricher = EnrichmentEngine(self.session, self.cost_tracker)
                enrichment_stats = enricher.enrich_all_pending(batch_size=batch_size)
                results["enrichment"] = enrichment_stats
                logger.info(f"Enrichment: {enrichment_stats}")

            if not skip_scoring:
                logger.info("--- Phase 3: Scoring ---")
                scorer = ScoringEngine(self.session, self.cost_tracker)
                scoring_stats = scorer.score_all()
                results["scoring"] = scoring_stats
                logger.info(f"Scoring: {scoring_stats}")

            self.session.commit()

            cost_summary = self.cost_tracker.get_run_summary()
            results["cost_summary"] = cost_summary
            logger.info(f"Total cost: ${cost_summary['total_cost']:.4f}")
            logger.info(f"=== Pipeline Complete ===")

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            results["error"] = str(e)
            raise
        finally:
            self.session.close()

        return results

    def ingest_only(self, csv_path: str) -> dict:
        init_db()
        df = load_csv(csv_path)
        stats = ingest_to_db(self.session, df)
        self.session.close()
        return stats

    def enrich_only(self, batch_size: int = 10) -> dict:
        init_db()
        enricher = EnrichmentEngine(self.session, self.cost_tracker)
        stats = enricher.enrich_all_pending(batch_size=batch_size)
        self.session.commit()
        self.session.close()
        return stats

    def score_only(self) -> dict:
        init_db()
        scorer = ScoringEngine(self.session, self.cost_tracker)
        stats = scorer.score_all()
        self.session.close()
        return stats
