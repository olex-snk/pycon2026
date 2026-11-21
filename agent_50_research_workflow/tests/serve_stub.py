"""Starts one remote agent's A2A app with the stub model (no API key needed)."""
import importlib, pathlib, sys
import uvicorn
HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE)]
import stub_llm  # noqa: F401  (patches every LlmAgent to use the stub)
mod = importlib.import_module(sys.argv[1])
uvicorn.run(mod.a2a_app, host="localhost", port=int(sys.argv[2]), log_level="warning")
