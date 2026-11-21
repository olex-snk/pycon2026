# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Parallel research + synthesis pipeline, rewritten as an ADK 2.0 graph Workflow.

Graph:

    START ──┬──> RenewableEnergyResearcher ──┐
            ├──> EVResearcher ───────────────┼──> research_join ──> SynthesisAgent
            └──> CarbonCaptureResearcher ────┘

Requires: google-adk>=2.0.0
"""

import os

from google.adk import Agent, Workflow
from google.adk.tools import google_search
from google.adk.workflow import JoinNode

MODEL = os.getenv("ADK_MODEL", "gemini-3.8-flash")


# --- 1. Researcher nodes (fan-out branches) ---------------------------------
# In a Workflow edge, an Agent runs in `single_turn` mode by default: it gets
# only its node_input (here, the user's message from START) and its final text
# becomes the node's output. No output_key is needed - the JoinNode collects
# each branch's output directly.

renewable_energy_researcher = Agent(
    name="RenewableEnergyResearcher",
    model=MODEL,
    description="Researches renewable energy sources.",
    instruction="""
    You are an AI Research Assistant specializing in energy.
    Research the latest advancements in 'renewable energy sources'.
    Use the Google Search tool provided.
    Summarize your key findings concisely (1-2 sentences).
    Output *only* the summary.
    """,
    tools=[google_search],
)

ev_researcher = Agent(
    name="EVResearcher",
    model=MODEL,
    description="Researches electric vehicle technology.",
    instruction="""
    You are an AI Research Assistant specializing in transportation.
    Research the latest developments in 'electric vehicle technology'.
    Use the Google Search tool provided.
    Summarize your key findings concisely (1-2 sentences).
    Output *only* the summary.
    """,
    tools=[google_search],
)

carbon_capture_researcher = Agent(
    name="CarbonCaptureResearcher",
    model=MODEL,
    description="Researches carbon capture methods.",
    instruction="""
    You are an AI Research Assistant specializing in climate solutions.
    Research the current state of 'carbon capture methods'.
    Use the Google Search tool provided.
    Summarize your key findings concisely (1-2 sentences).
    Output *only* the summary.
    """,
    tools=[google_search],
)


# --- 2. Fan-in barrier --------------------------------------------------------
# Replaces ParallelAgent: waits for every incoming branch, then emits one dict
# keyed by predecessor node name, e.g.
#   {"RenewableEnergyResearcher": "...", "EVResearcher": "...",
#    "CarbonCaptureResearcher": "..."}
research_join = JoinNode(name="research_join")


# --- 3. Synthesis node --------------------------------------------------------
# Receives the joined dict as its node_input (single_turn mode: it sees only
# that input, not the full conversation), so the summaries no longer need to be
# templated in from session state.
synthesis_agent = Agent(
    name="SynthesisAgent",
    model=MODEL,
    description=(
        "Combines research findings from parallel agents into a structured, "
        "cited report, strictly grounded on provided inputs."
    ),
    instruction="""
    You are an AI Assistant responsible for combining research findings into a structured report.

    Your input is a set of research summaries keyed by the researcher that produced them:
      - RenewableEnergyResearcher -> Renewable Energy
      - EVResearcher              -> Electric Vehicles
      - CarbonCaptureResearcher   -> Carbon Capture

    Synthesize these summaries, clearly attributing findings to their source areas. Structure
    your response using headings for each topic. Ensure the report is coherent and integrates
    the key points smoothly.

    **Crucially: Your entire response MUST be grounded *exclusively* on the information in the
    input summaries. Do NOT add any external knowledge, facts, or details not present in them.**

    **Output Format:**

    ## Summary of Recent Sustainable Technology Advancements

    ### Renewable Energy Findings
    (Based on RenewableEnergyResearcher's findings)
    [Synthesize and elaborate *only* on the renewable energy input summary.]

    ### Electric Vehicle Findings
    (Based on EVResearcher's findings)
    [Synthesize and elaborate *only* on the EV input summary.]

    ### Carbon Capture Findings
    (Based on CarbonCaptureResearcher's findings)
    [Synthesize and elaborate *only* on the carbon capture input summary.]

    ### Overall Conclusion
    [Provide a brief (1-2 sentence) concluding statement that connects *only* the findings presented above.]

    Output *only* the structured report following this format. Do not include introductory or
    concluding phrases outside this structure, and strictly adhere to using only the provided
    input summary content.
    """,
    # No tools needed for merging.
)


# --- 4. The graph -------------------------------------------------------------
# Replaces SequentialAgent(ParallelAgent(...), merger):
#   - the nested tuple fans out from START to the three researchers (run concurrently)
#   - research_join fans them back in
#   - synthesis_agent has no outgoing edges, so it is the terminal node and its
#     output is the workflow's final output.
root_agent = Workflow(
    name="ResearchAndSynthesisPipeline",
    description="Coordinates parallel research and synthesizes the results.",
    edges=[
        (
            "START",
            (renewable_energy_researcher, ev_researcher, carbon_capture_researcher),
            research_join,
            synthesis_agent,
        ),
    ],
)