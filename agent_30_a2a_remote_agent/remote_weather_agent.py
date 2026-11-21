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

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.a2a.utils.agent_to_a2a import to_a2a
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import uvicorn
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables from .env file
try:    
    env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    print(f"Loading .env from {env_file}")
    load_dotenv(dotenv_path=env_file)
except Exception as e:
    print(f"Error loading .env file: {e}")

MODEL = os.getenv("ADK_MODEL", "gemini-3.8-flash")

def get_weather(city: str) -> dict:
    """Retrieves the current weather report for a specified city.

    Args:
        city (str): The name of the city (e.g., "New York", "London", "Tokyo").

    Returns:
        dict: A dictionary containing the weather information.
              Includes a 'status' key ('success' or 'error').
              If 'success', includes a 'report' key with weather details.
              If 'error', includes an 'error_message' key.
    """
    print(
        f"--- Tool: get_weather called for city: {city} ---"
    )  # Log tool execution
    city_normalized = city.lower().replace(" ", "")  # Basic normalization

    # Mock weather data
    mock_weather_db = {
        "newyork": {
            "status": "success",
            "report": "The weather in New York is sunny with a temperature of 25°C.",
        },
        "dublin": {
            "status": "success",
            "report": "It's cloudy in Dublin with a temperature of 15°C.",
        },
        "tokyo": {
            "status": "success",
            "report": "Tokyo is experiencing light rain and a temperature of 18°C.",
        },
    }

    if city_normalized in mock_weather_db:
        return mock_weather_db[city_normalized]
    else:
        return {
            "status": "error",
            "error_message": f"Sorry, I don't have weather information for '{city}'.",
        }

weather_agent = Agent(
    name="remote_weather_agent",  # Give it a new version name
    model=MODEL,
    description="Handles weather information requests using the 'get_weather' tool.",
    instruction="You are the Weather Agent. Your primary responsibility is to provide weather information. "
    "Use the 'get_weather' tool for weather requests (e.g., 'weather in London'). "
    "Do not perform any other actions.",
    tools=[get_weather],
)
#root_agent = weather_agent

# Make the agent A2A-compatible
# a2a_app = to_a2a(root_agent, port=10020)

#from agent import root_agent
a2a_app = to_a2a(weather_agent, port=10020)

def main():
    port = 10020
    host = "[IP_ADDRESS]"
    base_url = f"http://localhost:{port}"

    # Make the agent A2A-compatible
    #a2a_app = to_a2a(weather_agent, port=10020)

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