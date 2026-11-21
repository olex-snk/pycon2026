"""Paper scout: a specialist that wraps an external API (arXiv), exposed over A2A (port 8002)."""
import os
import xml.etree.ElementTree as ET

import httpx
from google.adk import Agent
from google.adk.a2a.utils.agent_to_a2a import to_a2a

MODEL = os.getenv("ADK_MODEL", "gemini-3.5-flash")
ARXIV_URL = "https://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"


async def search_arxiv(query: str, max_results: int = 5) -> dict:
  """Searches arXiv for recent papers matching the query.

  Args:
    query: Keywords, e.g. "multi-agent LLM orchestration".
    max_results: Number of papers to return (1-10).

  Returns:
    A dict with a list of papers (title, summary, url, published) or an error.
  """
  params = {
      "search_query": f"all:{query}",
      "max_results": max(1, min(max_results, 10)),
      "sortBy": "submittedDate",
  }
  try:
    async with httpx.AsyncClient(timeout=15) as client:
      resp = await client.get(ARXIV_URL, params=params)
      resp.raise_for_status()
  except httpx.HTTPError as e:
    # Return errors as data so the model can recover instead of crashing.
    return {"status": "error", "message": str(e)}

  root = ET.fromstring(resp.text)
  papers = [
      {
          "title": e.findtext(f"{ATOM}title", "").strip(),
          "summary": e.findtext(f"{ATOM}summary", "").strip()[:600],
          "url": e.findtext(f"{ATOM}id", ""),
          "published": e.findtext(f"{ATOM}published", ""),
      }
      for e in root.findall(f"{ATOM}entry")
  ]
  return {"status": "ok", "papers": papers}


root_agent = Agent(
    name="paper_scout",
    model=MODEL,
    description="Finds and summarizes recent academic papers from arXiv.",
    instruction="""
    You find academic evidence. For each research question:
    - Call search_arxiv with 2-4 precise keywords.
    - Pick the 2-3 most relevant papers and summarize each in 2 sentences.
    - Always include the arXiv URL. If the tool returns an error, say so plainly.
    """,
    tools=[search_arxiv],
)

a2a_app = to_a2a(root_agent, port=8002)
