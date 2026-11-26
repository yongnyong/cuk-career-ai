"""Authored scenario, never presented as a live Gemini response."""
import json
from pathlib import Path

from .startup_plan import StartupPlan
from .startup_generation import fingerprint


def seojun_plan():
    # Keep the fixture in app/ so the API-only Docker image includes it.
    path = Path(__file__).with_name("startup_demo.json")
    plan = StartupPlan.model_validate(json.loads(path.read_text(encoding="utf-8")))
    plan.generation_fingerprint = fingerprint(plan)
    return plan
