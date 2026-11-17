"""The role runner. A role is a written skill (exposit/skills/<role>.md) plus a schema.
Input goes in as JSON, output must come back as JSON that validates."""
from __future__ import annotations
import json, re
from pydantic import BaseModel, ValidationError
from . import config, providers, schemas

ROLES = {
    "researcher": ("Researcher", schemas.Facts),
    "creative_director": ("Creative Director", schemas.Strategy),
    "storyteller": ("Storyteller", schemas.Script),
    "visual_planner": ("Visual Planner", schemas.Storyboard),
    "scene_editor": ("Animation Producer", schemas.SceneSpec),
    "reviewer": ("Quality Reviewer", schemas.Review),
}
# The seventh role, Audio Producer, is deterministic code (tts.py, sound.py): no model call.


def skill(role: str) -> str:
    return (config.SKILLS / f"{role}.md").read_text(encoding="utf-8")


def extract_json(text: str):
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1).strip()
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0] or [0])
    dec = json.JSONDecoder()
    obj, _ = dec.raw_decode(text[start:])
    return obj


def run(role: str, payload: dict, meta: dict | None = None) -> BaseModel:
    name, model = ROLES[role]
    system = (f"You are the {name} of Exposit Studio, a studio that makes accurate technical explainer videos.\n\n"
              + skill(role) + "\n\nReturn ONLY one JSON object, no prose before or after.")
    user = json.dumps(payload, ensure_ascii=False, indent=1)
    last_err = ""
    for attempt in range(2):
        prompt = user if not last_err else user + "\n\nYour previous answer was rejected: " + last_err + "\nReturn corrected JSON only."
        raw = providers.complete(system, prompt, role, meta)
        try:
            return model.model_validate(extract_json(raw))
        except (ValidationError, ValueError, json.JSONDecodeError) as e:
            last_err = str(e)[:600]
    raise providers.ProviderError(f"The {name} returned output that does not match its schema: {last_err}")
