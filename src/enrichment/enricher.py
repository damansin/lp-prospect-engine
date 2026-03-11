import json
import logging
import time
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from src.models import Organization
from src.enrichment.web_search import WebSearchClient
from src.enrichment.llm_analyzer import LLMAnalyzer
from src.cost_tracker import CostTracker
from src.config import TAVILY_CONCURRENT_LIMIT, TAVILY_DELAY_BETWEEN_BATCHES

logger = logging.getLogger(__name__)


class EnrichmentEngine:
    def __init__(self, session: Session, cost_tracker: CostTracker):
        self.session = session
        self.cost_tracker = cost_tracker
        self.search_client = WebSearchClient()
        self.llm_analyzer = LLMAnalyzer()

    def enrich_all_pending(self, batch_size: int = 10) -> dict:
        pending = (
            self.session.query(Organization)
            .filter(Organization.enrichment_status.in_(["pending", "error"]))
            .all()
        )
        total = len(pending)
        logger.info(f"Found {total} organizations to enrich")

        stats = {"total": total, "success": 0, "failed": 0, "skipped": 0}

        for i in range(0, total, batch_size):
            batch = pending[i : i + batch_size]
            logger.info(f"Processing batch {i // batch_size + 1} ({len(batch)} orgs)")

            for org in batch:
                try:
                    self._enrich_single(org)
                    stats["success"] += 1
                except Exception as e:
                    logger.error(f"Failed to enrich '{org.name}': {e}")
                    org.enrichment_status = "error"
                    org.enrichment_error = str(e)[:500]
                    self.session.commit()
                    stats["failed"] += 1

            if i + batch_size < total:
                time.sleep(TAVILY_DELAY_BETWEEN_BATCHES)

        logger.info(
            f"Enrichment complete: {stats['success']} success, "
            f"{stats['failed']} failed, {stats['skipped']} skipped"
        )
        return stats

    def _enrich_single(self, org: Organization):
        logger.info(f"Enriching: {org.name} ({org.org_type})")
        org.enrichment_status = "enriching"
        self.session.commit()

        search_data = self.search_client.search_organization(org.name, org.org_type or "")
        num_queries = search_data.get("total_queries", 0)
        self.cost_tracker.log_tavily_search(org.name, num_queries)

        analysis, tokens_in, tokens_out = self.llm_analyzer.analyze_organization(
            org_name=org.name,
            org_type=org.org_type or "",
            region=org.region or "",
            search_data=search_data,
        )
        self.cost_tracker.log_openai_call(org.name, "enrichment_analysis", tokens_in, tokens_out)

        org.enrichment_data = json.dumps(analysis)
        org.aum_estimated = analysis.get("aum_estimated", "Unknown")
        org.investment_mandate = analysis.get("investment_mandate", "Unknown")
        org.sustainability_focus = analysis.get("sustainability_focus", "None found")
        org.emerging_mgr_programs = analysis.get("emerging_manager_signals", "None found")
        org.is_lp = analysis.get("is_lp", "Unclear")
        org.enrichment_status = "done"
        org.enrichment_error = None
        org.enriched_at = datetime.now(timezone.utc)
        self.session.commit()

        logger.info(
            f"  -> {org.name}: LP={org.is_lp}, AUM={org.aum_estimated}, "
            f"Sector={analysis.get('sector_fit_score')}, "
            f"Halo={analysis.get('halo_value_score')}, "
            f"Emerging={analysis.get('emerging_fit_score')}"
        )

    def enrich_single_by_name(self, org_name: str) -> Organization | None:
        org = self.session.query(Organization).filter_by(name=org_name).first()
        if not org:
            logger.warning(f"Organization not found: {org_name}")
            return None
        self._enrich_single(org)
        return org
