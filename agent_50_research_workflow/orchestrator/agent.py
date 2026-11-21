"""Research & Report orchestrator: an ADK 2.x graph Workflow that calls
two remote specialists over A2A, then writes, critiques and gates a report."""
import os
from typing import Literal

from google.adk import Agent, Event, Workflow
from google.adk.agents.remote_a2a_agent import (
    AGENT_CARD_WELL_KNOWN_PATH,
    RemoteA2aAgent,
)
from google.adk.events import RequestInput
from google.adk.workflow import JoinNode
from pydantic import BaseModel, Field

MODEL = os.getenv("ADK_MODEL", "gemini-3.5-flash")
WEB_URL = os.getenv("WEB_RESEARCHER_URL", "http://localhost:8001")
PAPERS_URL = os.getenv("PAPER_SCOUT_URL", "http://localhost:8002")
MAX_REVISIONS = 2


# ---------- Typed contracts between steps ----------
class ResearchPlan(BaseModel):
  questions: list[str] = Field(description="3-5 specific research questions.")
  audience: str = Field(description="Who the report is for.")


class Review(BaseModel):
  verdict: Literal["approve", "revise"]
  feedback: str = Field(description="Concrete fixes if verdict is 'revise'.")


# ---------- 1. Intake + planning ----------
def intake(node_input: str):
  return Event(state={"topic": node_input, "feedback": "", "revisions": 0})


planner = Agent(
    name="planner",
    model=MODEL,
    instruction="""
    Break the topic "{topic}" into 3-5 specific, answerable research questions
    and infer the audience. Do not answer the questions.
    """,
    output_schema=ResearchPlan,
    output_key="plan",
)


def to_brief(node_input: ResearchPlan):
  # Remote agents do NOT see our session state, only session *content*.
  # Emit the brief as a message so it travels in the A2A request.
  brief = "Research these questions:\n" + "\n".join(
      f"{i}. {q}" for i, q in enumerate(node_input.questions, 1)
  )
  yield Event(message=brief)


# ---------- 2. Fan-out to remote specialists over A2A ----------
web_researcher = RemoteA2aAgent(
    name="web_researcher",
    description="Searches the public web and returns cited findings.",
    agent_card=f"{WEB_URL}{AGENT_CARD_WELL_KNOWN_PATH}",
)

paper_scout = RemoteA2aAgent(
    name="paper_scout",
    description="Finds and summarizes recent academic papers.",
    agent_card=f"{PAPERS_URL}{AGENT_CARD_WELL_KNOWN_PATH}",
)

gather = JoinNode(name="gather")


def _remote_text(ctx, node_input: dict, name: str) -> str:
  """JoinNode output is keyed by predecessor name. A streaming A2A peer can
  finish with a text-less 'completed' event, leaving the node output empty,
  so fall back to the last text the remote agent sent in this session."""
  if node_input.get(name):
    return str(node_input[name])
  for ev in reversed(ctx.session.events):
    if ev.author == name and ev.content and ev.content.parts:
      text = "".join(p.text or "" for p in ev.content.parts if not p.thought)
      if text:
        return text
  return f"[{name} returned no findings]"


def merge(ctx, node_input: dict):
  return Event(
      state={
          "web_findings": _remote_text(ctx, node_input, "web_researcher"),
          "paper_findings": _remote_text(ctx, node_input, "paper_scout"),
      }
  )


# ---------- 3. Write -> critique -> revise loop ----------
writer = Agent(
    name="writer",
    model=MODEL,
    instruction="""
    Write a concise research report on "{topic}".
    Use ONLY these findings and keep their citations:
    WEB: {web_findings}
    PAPERS: {paper_findings}
    Reviewer feedback to address (may be empty): {feedback?}
    Structure: Executive summary, Key findings, Open questions, Sources.
    """,
    output_key="draft",
)

critic = Agent(
    name="critic",
    model=MODEL,
    instruction="""
    Review this draft: {draft}
    Approve only if every claim has a citation and it answers the topic "{topic}".
    """,
    output_schema=Review,
)


def quality_gate(node_input: Review, revisions: int):
  # Deterministic loop bound: never trust the LLM to stop itself.
  if node_input.verdict == "approve" or revisions >= MAX_REVISIONS:
    yield Event(route="ready")
  else:
    yield Event(
        state={"feedback": node_input.feedback, "revisions": revisions + 1},
        route="revise",
    )


# ---------- 4. Human-in-the-loop approval ----------
class Approval(BaseModel):
  approved: bool
  feedback: str | None = None


def human_approval(draft: str):
  # Pauses the workflow (durably) until a human answers.
  yield RequestInput(message=f"Approve this report?\n\n{draft}",
                     response_schema=Approval)


def handle_approval(node_input: Approval):
  if node_input.approved:
    yield Event(route="publish")
  else:
    yield Event(state={"feedback": node_input.feedback or ""}, route="revise")


def publish(draft: str):
  yield Event(message=draft)


root_agent = Workflow(
    name="research_report",
    edges=[
        ("START", intake, planner, to_brief, (web_researcher, paper_scout), gather,
         merge, writer, critic, quality_gate),
        (quality_gate, {"revise": writer, "ready": human_approval}),
        (human_approval, handle_approval),
        (handle_approval, {"revise": writer, "publish": publish}),
    ],
)
