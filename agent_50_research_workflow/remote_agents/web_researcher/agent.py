"""Web researcher: a specialist agent exposed over A2A (port 8001)."""
import os

from google.adk import Agent
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.tools import google_search

MODEL = os.getenv("ADK_MODEL", "gemini-3.5-flash")

root_agent = Agent(
    name="web_researcher",
    model=MODEL,
    description="Searches the public web and returns cited findings.",
    instruction="""
    You are a web research specialist. For each research question you receive:
    - Run focused searches with google_search.
    - Return 3-5 findings per question as bullet points.
    - Every finding MUST end with its source URL in [brackets].
    - If sources disagree, say so. Never invent a source.
    """,
    tools=[google_search],
)

# One line turns the agent into an A2A server with an auto-generated Agent Card
# at /.well-known/agent-card.json
a2a_app = to_a2a(root_agent, port=8001)
