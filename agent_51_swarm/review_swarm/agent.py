"""Parallel 'swarm' in ADK 2.x: one reviewer agent, cloned per review angle.

parallel_worker=True runs the agent once per item of a list input, concurrently
(capped by max_parallel_workers), and hands the next node a list of results.
"""
import os
from typing import Literal

from google.adk import Agent, Event, Workflow
from pydantic import BaseModel

MODEL = os.getenv("ADK_MODEL", "gemini-3.5-flash")
ANGLES = ["security", "performance", "error handling", "readability", "test coverage"]


class Finding(BaseModel):
  angle: str
  severity: Literal["none", "low", "medium", "high"]
  summary: str


def fan_out(node_input: str):
  # Keep the diff in state; emit one task per angle (the list drives the swarm size).
  yield Event(state={"diff": node_input})
  yield [f"Review angle: {a}" for a in ANGLES]


reviewer = Agent(
    name="reviewer",
    model=MODEL,
    instruction="Review this diff ONLY from the angle in the message. Diff:\n{diff}",
    output_schema=Finding,
    parallel_worker=True,          # one run per list item
    #max_parallel_workers=3,        # concurrency cap (rate limits, cost)
)


def aggregate(node_input: list[Finding]):
  order = {"high": 0, "medium": 1, "low": 2, "none": 3}
  lines = [f"- [{f.severity.upper()}] {f.angle}: {f.summary}"
           for f in sorted(node_input, key=lambda f: order[f.severity])]
  return Event(message="Review swarm results:\n" + "\n".join(lines))


root_agent = Workflow(name="review_swarm", edges=[("START", fan_out, reviewer, aggregate)])
