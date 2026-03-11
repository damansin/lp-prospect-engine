import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from src.models import ApiCost
from src.config import COST_TAVILY_PER_SEARCH, COST_OPENAI_INPUT_PER_1M, COST_OPENAI_OUTPUT_PER_1M

logger = logging.getLogger(__name__)


class CostTracker:
    def __init__(self, session: Session, run_id: str):
        self.session = session
        self.run_id = run_id
        self._running_total = 0.0

    def log_tavily_search(self, organization: str, num_queries: int = 1):
        cost = COST_TAVILY_PER_SEARCH * num_queries
        entry = ApiCost(
            run_id=self.run_id,
            service="tavily",
            operation="enrichment_search",
            organization=organization,
            tokens_input=0,
            tokens_output=0,
            estimated_cost=cost,
            timestamp=datetime.now(timezone.utc),
        )
        self.session.add(entry)
        self._running_total += cost
        return cost

    def log_openai_call(self, organization: str, operation: str,
                        tokens_input: int, tokens_output: int):
        cost = (
            (tokens_input / 1_000_000) * COST_OPENAI_INPUT_PER_1M
            + (tokens_output / 1_000_000) * COST_OPENAI_OUTPUT_PER_1M
        )
        entry = ApiCost(
            run_id=self.run_id,
            service="openai",
            operation=operation,
            organization=organization,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            estimated_cost=cost,
            timestamp=datetime.now(timezone.utc),
        )
        self.session.add(entry)
        self._running_total += cost
        return cost

    @property
    def total_cost(self) -> float:
        return self._running_total

    def get_run_summary(self) -> dict:
        costs = self.session.query(ApiCost).filter_by(run_id=self.run_id).all()
        summary = {
            "run_id": self.run_id,
            "total_cost": sum(c.estimated_cost for c in costs),
            "total_api_calls": len(costs),
            "tavily_calls": sum(1 for c in costs if c.service == "tavily"),
            "openai_calls": sum(1 for c in costs if c.service == "openai"),
            "total_tokens_input": sum(c.tokens_input for c in costs),
            "total_tokens_output": sum(c.tokens_output for c in costs),
            "by_service": {},
        }
        for c in costs:
            if c.service not in summary["by_service"]:
                summary["by_service"][c.service] = 0.0
            summary["by_service"][c.service] += c.estimated_cost
        return summary
