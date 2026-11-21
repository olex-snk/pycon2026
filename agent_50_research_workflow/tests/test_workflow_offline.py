"""Offline integration test: real A2A servers + full workflow, stubbed model.

Run from the repo root:  python tests/test_workflow_offline.py
"""
import asyncio, pathlib, subprocess, sys, time
import httpx
HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE)]
import stub_llm
from google.adk import Runner
from google.adk.apps import App, ResumabilityConfig
from google.adk.sessions import InMemorySessionService
from google.adk.workflow.utils._workflow_hitl_utils import create_request_input_response
from google.genai import types
from orchestrator import agent as orch


def start_servers():
  procs = [subprocess.Popen([sys.executable, str(HERE / "serve_stub.py"), m, p])
           for m, p in [("remote_agents.web_researcher.agent", "8001"),
                        ("remote_agents.paper_scout.agent", "8002")]]
  for port in (8001, 8002):
    for _ in range(60):
      try:
        httpx.get(f"http://localhost:{port}/.well-known/agent-card.json").raise_for_status(); break
      except Exception:
        time.sleep(0.5)
  return procs


async def run():
  app = App(name="research_report", root_agent=orch.root_agent,
            resumability_config=ResumabilityConfig(is_resumable=True))
  ss = InMemorySessionService(); runner = Runner(app=app, session_service=ss)
  s = await ss.create_session(app_name="research_report", user_id="u")
  msg = types.Content(role="user", parts=[types.Part(text="State of multi-agent LLM systems")])
  ask = None
  async for ev in runner.run_async(user_id="u", session_id=s.id, new_message=msg):
    for fc in ev.get_function_calls():
      if fc.name == "adk_request_input":
        ask = (fc.args["interruptId"], ev.invocation_id)
  assert ask, "workflow did not pause for human approval"
  part = create_request_input_response(ask[0], {"approved": True})
  async for _ in runner.run_async(user_id="u", session_id=s.id, invocation_id=ask[1],
                                  new_message=types.Content(role="user", parts=[part])):
    pass
  st = (await ss.get_session(app_name="research_report", user_id="u", session_id=s.id)).state
  assert "WEB-FINDING" in st["web_findings"], st["web_findings"]
  assert "PAPER-FINDING" in st["paper_findings"], st["paper_findings"]
  assert "BRIEF-RECEIVED" in st["web_findings"] and "BRIEF-RECEIVED" in st["paper_findings"], "brief did not reach remote agent"
  assert st["revisions"] == 1, st["revisions"]
  print("OK: plan -> A2A fan-out -> join -> write/critique loop -> human approval -> publish")


if __name__ == "__main__":
  procs = start_servers()
  try:
    asyncio.run(run())
  finally:
    for p in procs: p.terminate()
