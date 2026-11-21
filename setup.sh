#!/bin/bash
#export PATH=$PATH:~/.local/bin
uvx google-agents-cli setup
agents-cli install
source .venv/bin/activate
adk telemetry disable
export ADK_TELEMETRY=false
