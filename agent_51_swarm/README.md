# Agent Swarm examples for ADK 2.x

Tested with google-adk 2.15.0 (Python 3.11+). `pip install google-adk`, set `GOOGLE_API_KEY`.

## 1. `incident_swarm/`: handoff swarm (no central planner)

`triage` is the entry point; `log_analyst`, `db_expert` and `comms` are its sub-agents and
therefore **peers**. Each agent hands the conversation directly to whichever peer should act
next with ADK's built-in `transfer_to_agent`; peer transfer is on by default
(`disallow_transfer_to_peers=False`).

- **Shared blackboard**: `add_note` writes to `state["incident_notes"]`; every instruction
  renders `{incident_notes?}`, so the agent that receives a handoff sees the findings so far.
- **Handoff cap**: a `before_tool_callback` counts `transfer_to_agent` calls and, past
  `MAX_HANDOFFS`, returns an error instead of transferring (returning a dict skips the tool).
- **Sticky active agent**: the next user message goes to the last agent that spoke, not back
  to triage.

```bash
adk web .          # pick incident_swarm, try: "Checkout is slow for everyone!"
python tests/test_swarm_offline.py
```

## 2. `review_swarm/`: parallel swarm (many workers, one job)

A `Workflow` sends one list item per review angle to a single `reviewer` agent marked
`parallel_worker=True`, so ADK runs a copy per item concurrently (capped by
`max_parallel_workers`) and passes the list of typed `Finding`s to `aggregate`.

```bash
python tests/test_review_swarm_offline.py
```

## Which one?

| | Handoff swarm | Parallel swarm |
|---|---|---|
| Path | Chosen at run time by the agents | Fixed: fan out, then aggregate |
| Agents | Different specialists | Copies of one agent (or a tuple of different ones) |
| Good for | Conversations, triage, investigations | Reviews, batch analysis, research over N items |
| Main risk | Ping-pong and runaway cost | Rate limits, slowest worker sets latency |

Production notes: ADK warns that every transfer swaps the system instruction and tools, so
the prompt is re-sent uncached; set `context_cache_config` on the `App`. A swarm member can
also be a `RemoteA2aAgent` (default chat mode), which makes it a transfer target served by
another team.
