"""
Remote A2A Agent - Entry Point
"""

import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from starlette.middleware.cors import CORSMiddleware
from agent_30_a2a_remote_agent.remote_weather_agent import weather_agent as root_agent
from dotenv import load_dotenv

def main():
    port = 10020
    host = os.getenv("HOST", "0.0.0.0")
    base_url = f"http://localhost:{port}"

    a2a_app = to_a2a(root_agent, port=10020)

    a2a_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    uvicorn.run(a2a_app, host=host, port=port)


if __name__ == "__main__":
  # Load environment variables from .env file
  try:    
      env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
      print(f"Loading .env from {env_file}")
      load_dotenv(dotenv_path=env_file)
  except Exception as e:
      print(f"Error loading .env file: {e}")
  main()