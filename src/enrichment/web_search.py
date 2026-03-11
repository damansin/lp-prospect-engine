import logging
import asyncio
from tavily import TavilyClient
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from src.config import TAVILY_API_KEY, TAVILY_MAX_RESULTS

logger = logging.getLogger(__name__)


class WebSearchClient:
    def __init__(self):
        if not TAVILY_API_KEY:
            raise ValueError("TAVILY_API_KEY not set in environment")
        self.client = TavilyClient(api_key=TAVILY_API_KEY)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def search(self, query: str) -> list[dict]:
        results = self.client.search(
            query=query,
            max_results=TAVILY_MAX_RESULTS,
            search_depth="advanced",
        )
        return results.get("results", [])

    def search_organization(self, org_name: str, org_type: str) -> dict:
        """Run targeted searches for an organization, returning combined results."""
        queries = self._build_queries(org_name, org_type)
        all_results = {}
        total_queries = 0

        for label, query in queries.items():
            try:
                results = self.search(query)
                all_results[label] = [
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "content": r.get("content", ""),
                        "score": r.get("score", 0),
                    }
                    for r in results
                ]
                total_queries += 1
                logger.debug(f"  [{label}] {len(results)} results for: {query}")
            except Exception as e:
                logger.warning(f"  [{label}] Search failed for '{query}': {e}")
                all_results[label] = []
                total_queries += 1

        return {"queries": queries, "results": all_results, "total_queries": total_queries}

    def _build_queries(self, org_name: str, org_type: str) -> dict[str, str]:
        queries = {}

        if org_type in ("Foundation", "Endowment", "Pension"):
            queries["investment_profile"] = (
                f'"{org_name}" investment office portfolio allocations '
                f'private credit private debt direct lending fund commitments AUM'
            )
            queries["sustainability"] = (
                f'"{org_name}" ESG sustainability impact investing '
                f'climate responsible investment mandate'
            )
        elif org_type in ("Single Family Office", "Multi-Family Office", "HNWI"):
            queries["investment_profile"] = (
                f'"{org_name}" {org_type} external fund allocations '
                f'investment strategy portfolio AUM alternatives'
            )
            queries["sustainability"] = (
                f'"{org_name}" ESG sustainability impact '
                f'climate investing private credit debt'
            )
        elif org_type in ("Fund of Funds",):
            queries["investment_profile"] = (
                f'"{org_name}" fund of funds allocations strategy '
                f'private credit private debt hedge funds AUM'
            )
            queries["sustainability"] = (
                f'"{org_name}" ESG impact sustainability climate fund commitments'
            )
        elif org_type in ("Insurance",):
            queries["investment_profile"] = (
                f'"{org_name}" insurance investment portfolio '
                f'alternatives private credit private debt AUM allocations'
            )
            queries["sustainability"] = (
                f'"{org_name}" ESG sustainability responsible investing climate'
            )
        else:
            queries["investment_profile"] = (
                f'"{org_name}" {org_type} investment portfolio '
                f'fund allocations AUM private credit alternatives'
            )
            queries["sustainability"] = (
                f'"{org_name}" ESG sustainability impact investing climate'
            )

        queries["emerging_manager"] = (
            f'"{org_name}" emerging manager program first-time fund '
            f'new manager allocation small fund commitment'
        )

        return queries
