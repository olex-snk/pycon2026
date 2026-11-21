"""Offline test of the incident swarm: a scripted model drives the handoffs."""
import asyncio, collections, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from google.adk import Runner
from google.adk.agents.llm_agent import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.sessions import InMemorySessionService
from google.genai import types

FC = lambda name, **args: types.Part(function_call=types.FunctionCall(name=name, args=args))
TXT = lambda t: types.Part(text=t)
SCRIPTS = {
  "You receive incident reports": [FC("add_note", note="Checkout p99 > 8s since 14:02"),
                                   FC("transfer_to_agent", agent_name="log_analyst")],
  "You analyze service logs": [FC("search_logs", service="checkout-api", query="ERROR"),
                               FC("add_note", note="DB pool exhausted at 14:02; need DB diagnosis"),
                               FC("transfer_to_agent", agent_name="db_expert")],
  "You diagnose database": [FC("query_db_metrics", database="orders-primary"),
                            FC("add_note", note="50/50 connections, 37 slow queries; mitigate: raise pool, kill top query"),
                            FC("transfer_to_agent", agent_name="comms")],
  "You turn the board": [FC("post_status_update", message="Checkout degraded: DB pool exhausted..."),
                         TXT("Status update posted."), TXT("Still monitoring; next update in 30 min.")],
}
CALLS = collections.Counter(); SEEN = {}

class ScriptedLlm(BaseLlm):
  model: str = "gemini-3.5-flash"
  async def generate_content_async(self, req, stream=False):
    si = str(req.config.system_instruction or "")
    key = next(k for k in SCRIPTS if k in si)
    SEEN[key] = si
    part = SCRIPTS[key][CALLS[key]]; CALLS[key] += 1
    yield LlmResponse(content=types.Content(role="model", parts=[part]))

_LLM = ScriptedLlm()
LlmAgent.canonical_model = property(lambda self: _LLM)
from incident_swarm import agent as swarm

async def turn(runner, sid, text):
  authors, tools = [], []
  msg = types.Content(role="user", parts=[types.Part(text=text)])
  async for ev in runner.run_async(user_id="u", session_id=sid, new_message=msg):
    authors.append(ev.author)
    tools += [fc.name + (f"->{fc.args['agent_name']}" if fc.name == "transfer_to_agent" else "")
              for fc in ev.get_function_calls()]
  return authors, tools

async def main():
  ss = InMemorySessionService()
  runner = Runner(app_name="swarm", agent=swarm.root_agent, session_service=ss)
  s = await ss.create_session(app_name="swarm", user_id="u")

  authors, tools = await turn(runner, s.id, "Checkout is slow for everyone!")
  print("turn 1 path :", " > ".join(dict.fromkeys(a for a in authors if a != "user")))
  print("turn 1 tools:", tools)
  st = (await ss.get_session(app_name="swarm", user_id="u", session_id=s.id)).state
  assert st["handoffs"] == 3, st
  assert len(st["incident_notes"]) == 3
  assert "DB pool exhausted" in SEEN["You diagnose database"], "db_expert didn't see the board"

  authors, _ = await turn(runner, s.id, "Any news?")
  replier = [a for a in authors if a != "user"][0]
  print("turn 2 goes straight to:", replier)
  assert replier == "comms", "active agent was not remembered"

  # Guardrail: at the cap, the transfer tool is skipped and an error is returned.
  class FakeTool: name = "transfer_to_agent"
  class FakeCtx: state = {"handoffs": swarm.MAX_HANDOFFS}
  print("at cap      :", swarm.limit_handoffs(FakeTool(), {}, FakeCtx()))
  print("OK")

asyncio.run(main())
