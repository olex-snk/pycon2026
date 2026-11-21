"""Agent Swarm pattern in ADK 2.x: an incident-response swarm.

No central planner decides the path. Each specialist owns one skill and hands
the conversation directly to whichever peer should act next, using ADK's
built-in `transfer_to_agent` (peer transfer is on by default). The swarm shares
a "blackboard" in session state, and a callback caps the number of handoffs so
agents can't ping-pong forever.

    triage ──► log_analyst ◄──► db_expert ◄──► comms
                    ▲                              │
                    └──────────────────────────────┘   (any peer → any peer)
"""
import os

from google.adk import Agent
from google.adk.tools.tool_context import ToolContext

MODEL = os.getenv("ADK_MODEL", "gemini-3.8-flash")
MAX_HANDOFFS = 6


# ---------- Shared blackboard: every agent reads it, any agent can add to it ----------
def add_note(note: str, tool_context: ToolContext) -> dict:
  """Records a finding on the shared incident board for the other agents.

  Args:
    note: One short, factual finding, e.g. "p99 latency spike starts 14:02 UTC".
  """
  author = tool_context.agent_name
  notes = list(tool_context.state.get("incident_notes", []))
  notes.append(f"[{author}] {note}")
  tool_context.state["incident_notes"] = notes
  return {"status": "ok", "notes_on_board": len(notes)}


BOARD = """
Incident board (shared by the whole team, newest last):
{incident_notes?}

Rules for the team:
- Do your part with YOUR tools only, record each finding with add_note.
- When another specialist should act next, hand off with transfer_to_agent.
  Before handing off, add a note saying what you need from them.
- Never hand back to an agent just to say thanks.
"""


# ---------- Guardrail: cap handoffs so the swarm can't loop forever ----------
def limit_handoffs(tool, args, tool_context):
  """before_tool_callback: returning a dict skips the real tool call."""
  if tool.name != "transfer_to_agent":
    return None
  count = tool_context.state.get("handoffs", 0)
  if count >= MAX_HANDOFFS:
    return {"error": f"Handoff limit ({MAX_HANDOFFS}) reached. "
                     "Summarize the board for the user and stop."}
  tool_context.state["handoffs"] = count + 1
  return None  # proceed with the transfer


# ---------- Specialist tools (mocked: swap in your observability / DB / chat APIs) ----------
def search_logs(service: str, query: str) -> dict:
  """Searches recent logs of a service.

  Args:
    service: Service name, e.g. "checkout-api".
    query: Text or error code to look for.
  """
  return {"service": service, "matches": [
      "14:02:11 ERROR db pool exhausted (max=50) waiting=212",
      "14:02:15 WARN request timeout /v1/checkout p99=8.4s"]}


def query_db_metrics(database: str) -> dict:
  """Returns current health metrics for a database.

  Args:
    database: Database name, e.g. "orders-primary".
  """
  return {"database": database, "active_connections": 50, "max_connections": 50,
          "slow_queries_last_10m": 37, "top_query": "SELECT * FROM orders WHERE ..."}


def post_status_update(message: str) -> dict:
  """Posts a status update to the incident channel.

  Args:
    message: The update, written for engineers and support staff.
  """
  return {"status": "posted", "message": message}


# ---------- The swarm members ----------
log_analyst = Agent(
    name="log_analyst",
    model=MODEL,
    description="Finds errors and timelines in service logs.",
    instruction="You analyze service logs and establish the incident timeline." + BOARD,
    tools=[search_logs, add_note],
    before_tool_callback=limit_handoffs,
)

db_expert = Agent(
    name="db_expert",
    model=MODEL,
    description="Diagnoses database load, connections and slow queries.",
    instruction="You diagnose database problems and propose a mitigation." + BOARD,
    tools=[query_db_metrics, add_note],
    before_tool_callback=limit_handoffs,
)

comms = Agent(
    name="comms",
    model=MODEL,
    description="Writes and posts incident status updates.",
    instruction=(
        "You turn the board into a clear status update (impact, cause, next step) "
        "and post it with post_status_update. Then tell the user it is posted." + BOARD
    ),
    tools=[post_status_update, add_note],
    before_tool_callback=limit_handoffs,
)

# The entry point. Its sub_agents are peers of each other, so any of them can
# transfer directly to any other, or back to triage.
root_agent = Agent(
    name="triage",
    model=MODEL,
    description="Entry point: understands the report and picks the first specialist.",
    instruction=(
        "You receive incident reports. Record the symptom with add_note, then hand off "
        "to the specialist who should look first. Do not investigate yourself." + BOARD
    ),
    tools=[add_note],
    sub_agents=[log_analyst, db_expert, comms],
    before_tool_callback=limit_handoffs,
)
