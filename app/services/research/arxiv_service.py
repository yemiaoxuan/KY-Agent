import logging
import re

import arxiv

from app.models.topic import Topic
from app.schemas.paper import PaperCandidate

logger = logging.getLogger(__name__)


def _build_arxiv_query(topic: Topic, raw_query: str) -> str:
    category_query = " OR ".join(f"cat:{category}" for category in topic.arxiv_categories)
    if category_query:
        return f"({raw_query}) AND ({category_query})"
    return raw_query


def _candidate_queries(topic: Topic) -> list[str]:
    queries: list[str] = []
    seen: set[str] = set()
    raw_candidates = [
        topic.query.strip(),
        topic.name.strip(),
        topic.display_name.strip(),
        " OR ".join(keyword.strip() for keyword in topic.include_keywords if keyword.strip()),
    ]
    for item in raw_candidates:
        if item and item not in seen:
            seen.add(item)
            queries.append(item)
    return queries


def _extract_arxiv_id(entry_id: str) -> str:
    match = re.search(r"abs/([^v]+)(?:v\d+)?$", entry_id)
    if match:
        return match.group(1)
    return entry_id.rstrip("/").split("/")[-1]


def search_arxiv(topic: Topic) -> list[PaperCandidate]:
    client = arxiv.Client(page_size=min(topic.max_results, 100), delay_seconds=3, num_retries=3)
    last_candidates: list[PaperCandidate] = []
    for raw_query in _candidate_queries(topic):
        query = _build_arxiv_query(topic, raw_query)
        logger.info("Searching arXiv for topic=%s query=%s", topic.name, query)
        search = arxiv.Search(
            query=query,
            max_results=topic.max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )
        candidates: list[PaperCandidate] = []
        for result in client.results(search):
            candidates.append(
                PaperCandidate(
                    source_id=_extract_arxiv_id(result.entry_id),
                    title=" ".join(result.title.split()),
                    abstract=" ".join(result.summary.split()),
                    authors=[author.name for author in result.authors],
                    categories=list(result.categories),
                    published_at=result.published,
                    source_updated_at=result.updated,
                    url=result.entry_id,
                    pdf_url=result.pdf_url,
                )
            )
        if candidates:
            return candidates
        last_candidates = candidates
    return last_candidates
