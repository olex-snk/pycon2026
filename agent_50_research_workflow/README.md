# Research & Report: a multi-agent workflow with ADK 2.x and A2A

Demo code for the workshop *Building Multi-Agent Workflows with the Agent Development Kit (ADK)*.
Tested with google-adk 2.15.0 and a2a-sdk 1.3.1 on Python 3.13.

```
orchestrator/            ADK Workflow: plan -> A2A fan-out -> join -> writer/critic loop -> human approval
remote_agents/
  web_researcher/        Agent + google_search, served over A2A on :8001
  paper_scout/           Agent + arXiv API tool, served over A2A on :8002
tests/                   Offline integration test (stub model, real A2A servers, no API key)
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export GOOGLE_API_KEY=...            # or: GOOGLE_GENAI_USE_VERTEXAI=TRUE GOOGLE_CLOUD_PROJECT=... GOOGLE_CLOUD_LOCATION=...
export ADK_MODEL=gemini-3.5-flash    # optional, this is the default
```

## Run

```bash
# terminals 1 and 2: the remote specialists
uvicorn remote_agents.web_researcher.agent:a2a_app --port 8001
uvicorn remote_agents.paper_scout.agent:a2a_app --port 8002
curl -s localhost:8001/.well-known/agent-card.json

# terminal 3: the orchestrator in the ADK web UI
adk web .        # open http://localhost:8000 and pick "orchestrator"
```

Point the orchestrator at deployed specialists with `WEB_RESEARCHER_URL` and `PAPER_SCOUT_URL`.

## Test without an API key

```bash
python tests/test_workflow_offline.py
```

It starts both A2A servers with a stub model, runs the whole workflow, answers the approval
prompt, and checks that the brief reached both remote agents and that the critic loop ran once.

## Things this code works around (ADK 2.15)

- A function node's return value is not sent to a `RemoteA2aAgent`; the remote side sees session
  *content*. `to_brief` therefore yields `Event(message=...)`.
- With the default streaming A2A server, the final `completed` event carries no text, so the
  `JoinNode` can receive `None`. `merge` falls back to the remote agent's last text event.
- Session state does not cross the A2A boundary in either direction.
- The writer/critic loop is bounded in code (`MAX_REVISIONS`), not by the model.
