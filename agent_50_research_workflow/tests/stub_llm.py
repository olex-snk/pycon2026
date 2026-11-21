import json, itertools
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types

CRITIC_CALLS = itertools.count()
LOG = []

class StubLlm(BaseLlm):
  model: str = "gemini-3.5-flash"
  async def generate_content_async(self, llm_request, stream=False):
    si = str(llm_request.config.system_instruction or "")
    last = ""
    for c in llm_request.contents or []:
      for p in c.parts or []:
        if p.text: last = p.text
    got_brief = "BRIEF-RECEIVED" if any("Research these questions" in (p.text or "") for c in llm_request.contents or [] for p in c.parts or []) else "NO-BRIEF"
    if "research questions" in si and "Break the topic" in si:
      out = json.dumps({"questions": ["Q1 what?", "Q2 why?", "Q3 how?"], "audience": "Senior AI engineers"})
      who="planner"
    elif "Review this draft" in si:
      n = next(CRITIC_CALLS)
      out = json.dumps({"verdict": "revise" if n == 0 else "approve", "feedback": "Add a citation to finding 2."})
      who=f"critic#{n}"
    elif "concise research report" in si:
      out = f"REPORT v (feedback seen: {'citation' in si}) | has web: {'WEB-FINDING' in si} | has papers: {'PAPER-FINDING' in si}"
      who="writer"
    elif "web research specialist" in si:
      out = f"WEB-FINDING ({got_brief}) [https://example.com]"
      who="web_researcher(remote)"
    elif "academic evidence" in si:
      out = f"PAPER-FINDING ({got_brief}) [https://arxiv.org/abs/0000]"
      who="paper_scout(remote)"
    else:
      out = "??"; who="unknown"
    LOG.append(who)
    yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text=out)]))

from google.adk.agents.llm_agent import LlmAgent
_STUB = StubLlm()
LlmAgent.canonical_model = property(lambda self: _STUB)
