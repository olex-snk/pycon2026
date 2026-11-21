"""Offline test of the parallel review swarm with a stub model."""
import asyncio, json, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from google.adk import Runner
from google.adk.agents.llm_agent import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.sessions import InMemorySessionService
from google.genai import types

ACTIVE = {"now": 0, "max": 0}

class StubLlm(BaseLlm):
  model: str = "gemini-3.5-flash"
  async def generate_content_async(self, req, stream=False):
    ACTIVE["now"] += 1; ACTIVE["max"] = max(ACTIVE["max"], ACTIVE["now"])
    await asyncio.sleep(0.2)                       # simulate model latency
    ACTIVE["now"] -= 1
    text = " ".join(p.text or "" for c in req.contents for p in c.parts or [])
    angle = re.findall(r"Review angle: ([a-z ]+)", text)[-1]
    sev = "high" if angle == "security" else "low"
    yield LlmResponse(content=types.Content(role="model", parts=[types.Part(
        text=json.dumps({"angle": angle, "severity": sev, "summary": f"checked {angle}"}))]))

_LLM = StubLlm()
LlmAgent.canonical_model = property(lambda self: _LLM)
from review_swarm import agent as rs

async def main():
  ss = InMemorySessionService(); r = Runner(app_name="rs", agent=rs.root_agent, session_service=ss)
  s = await ss.create_session(app_name="rs", user_id="u")
  out = ""
  async for ev in r.run_async(user_id="u", session_id=s.id, new_message=types.Content(
      role="user", parts=[types.Part(text="def pay(x): eval(x)")])):
    if ev.author == "review_swarm" and ev.content and ev.content.parts and ev.content.parts[0].text:
      out = ev.content.parts[0].text
  print(out); print("peak concurrent model calls:", ACTIVE["max"])
  assert out.count("\n- [") == 5 and "[HIGH] security" in out.splitlines()[1]
  assert ACTIVE["max"] == 3, "max_parallel_workers not respected"
  print("OK")
asyncio.run(main())
