"""Mock research tools.

These emulate an article search backend (think Semantic Scholar / arXiv / a
news API) using a small in-memory corpus, so the agent can be developed and
tested without network access or API keys. Swap the bodies for real API calls
later; keep the signatures and return shapes the same.
"""

from __future__ import annotations

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Mock corpus
# ---------------------------------------------------------------------------
_ARTICLES: list[dict] = [
    {
        "id": "art-001",
        "title": "Attention Is All You Need",
        "authors": ["A. Vaswani", "N. Shazeer", "N. Parmar"],
        "year": 2017,
        "source": "NeurIPS",
        "url": "https://example.org/articles/art-001",
        "tags": ["transformers", "nlp", "deep learning", "attention"],
        "abstract": (
            "Introduces the Transformer, an architecture based solely on "
            "attention mechanisms, dispensing with recurrence and convolutions. "
            "Achieves state-of-the-art results on machine translation."
        ),
        "key_findings": [
            "Self-attention replaces recurrence for sequence modeling.",
            "Training is significantly more parallelizable than RNNs.",
            "Sets new BLEU records on WMT 2014 EN-DE and EN-FR.",
        ],
    },
    {
        "id": "art-002",
        "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
        "authors": ["P. Lewis", "E. Perez", "A. Piktus"],
        "year": 2020,
        "source": "NeurIPS",
        "url": "https://example.org/articles/art-002",
        "tags": ["rag", "retrieval", "nlp", "llm", "question answering"],
        "abstract": (
            "Combines a pretrained seq2seq model with a dense retriever over "
            "Wikipedia, improving factuality on open-domain QA."
        ),
        "key_findings": [
            "Retrieval reduces hallucination on knowledge-intensive tasks.",
            "Index can be updated without retraining the generator.",
        ],
    },
    {
        "id": "art-003",
        "title": "Scaling Laws for Neural Language Models",
        "authors": ["J. Kaplan", "S. McCandlish", "T. Henighan"],
        "year": 2020,
        "source": "arXiv",
        "url": "https://example.org/articles/art-003",
        "tags": ["scaling", "llm", "deep learning", "compute"],
        "abstract": (
            "Studies empirical scaling laws for language model loss as a "
            "function of model size, dataset size and compute."
        ),
        "key_findings": [
            "Loss follows power laws in parameters, data and compute.",
            "Larger models are more sample-efficient.",
        ],
    },
    {
        "id": "art-004",
        "title": "ReAct: Synergizing Reasoning and Acting in Language Models",
        "authors": ["S. Yao", "J. Zhao", "D. Yu"],
        "year": 2023,
        "source": "ICLR",
        "url": "https://example.org/articles/art-004",
        "tags": ["agents", "llm", "reasoning", "tool use"],
        "abstract": (
            "Interleaves reasoning traces with task-specific actions, letting "
            "LLMs call tools such as search and use the results."
        ),
        "key_findings": [
            "Reasoning + acting outperforms either alone on HotpotQA and FEVER.",
            "Traces make agent behaviour more interpretable.",
        ],
    },
    {
        "id": "art-005",
        "title": "Global Warming of 1.5°C: Summary for Policymakers",
        "authors": ["IPCC"],
        "year": 2018,
        "source": "IPCC Special Report",
        "url": "https://example.org/articles/art-005",
        "tags": ["climate", "climate change", "policy", "emissions"],
        "abstract": (
            "Assesses impacts of 1.5°C warming above pre-industrial levels and "
            "related emission pathways."
        ),
        "key_findings": [
            "Limiting warming to 1.5°C needs net-zero CO2 around 2050.",
            "Impacts at 2°C are substantially worse than at 1.5°C.",
        ],
    },
    {
        "id": "art-006",
        "title": "Renewable Energy Cost Trends 2010–2023",
        "authors": ["M. Taylor", "L. Ruiz"],
        "year": 2024,
        "source": "Energy Policy Journal",
        "url": "https://example.org/articles/art-006",
        "tags": ["renewable energy", "solar", "wind", "climate", "economics"],
        "abstract": (
            "Reviews levelized cost of electricity for solar PV and onshore "
            "wind over the past decade."
        ),
        "key_findings": [
            "Utility-scale solar LCOE fell by roughly 90% since 2010.",
            "Onshore wind is now cheaper than new fossil generation in most markets.",
        ],
    },
    {
        "id": "art-007",
        "title": "Effects of Intermittent Fasting on Metabolic Health: A Meta-Analysis",
        "authors": ["R. Chen", "K. Patel"],
        "year": 2022,
        "source": "Journal of Nutrition",
        "url": "https://example.org/articles/art-007",
        "tags": ["health", "nutrition", "fasting", "metabolism"],
        "abstract": (
            "Meta-analysis of 27 RCTs comparing intermittent fasting with "
            "continuous calorie restriction."
        ),
        "key_findings": [
            "Weight loss is comparable to continuous calorie restriction.",
            "Modest improvements in insulin sensitivity.",
            "Evidence quality is moderate; long-term data are limited.",
        ],
    },
]

_ARTICLES_BY_ID = {a["id"]: a for a in _ARTICLES}


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _score(article: dict, query_tokens: set[str]) -> int:
    """Naive relevance: title/tag hits weigh more than abstract hits."""
    title = _tokenize(article["title"])
    tags = _tokenize(" ".join(article["tags"]))
    abstract = _tokenize(article["abstract"])
    return (
        3 * len(query_tokens & title)
        + 3 * len(query_tokens & tags)
        + 1 * len(query_tokens & abstract)
    )


# ---------------------------------------------------------------------------
# Tools exposed to the agent
# ---------------------------------------------------------------------------
def search_articles(
    query: str,
    max_results: int = 5,
    year_from: Optional[int] = None,
) -> dict:
    """Searches for articles and papers relevant to a research query.

    Args:
        query: Keywords or a short natural-language research question,
            e.g. "retrieval augmented generation" or "solar energy cost".
        max_results: Maximum number of articles to return (1-10). Defaults to 5.
        year_from: Optional. Only return articles published in or after this year.

    Returns:
        dict: On success, {"status": "success", "query": ..., "total_found": int,
        "results": [{"id", "title", "authors", "year", "source", "url",
        "snippet"}]}. On failure, {"status": "error", "error_message": str}.
    """
    if not query or not query.strip():
        return {"status": "error", "error_message": "Query must not be empty."}

    max_results = max(1, min(int(max_results), 10))
    query_tokens = _tokenize(query)

    scored = []
    for article in _ARTICLES:
        if year_from is not None and article["year"] < year_from:
            continue
        score = _score(article, query_tokens)
        if score > 0:
            scored.append((score, article))

    scored.sort(key=lambda pair: (pair[0], pair[1]["year"]), reverse=True)

    if not scored:
        return {
            "status": "error",
            "error_message": f"No articles found for '{query}'. "
            "Try broader or different keywords.",
        }

    results = [
        {
            "id": a["id"],
            "title": a["title"],
            "authors": a["authors"],
            "year": a["year"],
            "source": a["source"],
            "url": a["url"],
            "snippet": a["abstract"][:160] + ("..." if len(a["abstract"]) > 160 else ""),
        }
        for _, a in scored[:max_results]
    ]
    return {
        "status": "success",
        "query": query,
        "total_found": len(scored),
        "results": results,
    }


def get_article_details(article_id: str) -> dict:
    """Retrieves the full abstract and key findings of an article.

    Use this after search_articles when a result looks relevant and you need
    more than the snippet to answer accurately.

    Args:
        article_id: The "id" field from a search_articles result, e.g. "art-002".

    Returns:
        dict: On success, {"status": "success", "article": {...full record...}}.
        On failure, {"status": "error", "error_message": str}.
    """
    article = _ARTICLES_BY_ID.get((article_id or "").strip())
    if article is None:
        return {
            "status": "error",
            "error_message": f"Article '{article_id}' not found.",
        }
    return {"status": "success", "article": dict(article)}
