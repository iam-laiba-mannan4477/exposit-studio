"""Schemas for every artefact a role produces. The Director rejects output that does not validate."""
from __future__ import annotations
from typing import Any, Literal, Optional, Union
from pydantic import BaseModel, Field

Tier = Literal["verified", "preference", "observation", "hypothesis", "experiment"]
TREATMENTS = ["iconflow", "map", "sequence", "cards", "compare", "stat",
              "kinetic", "flow2d", "isometric", "cutaway", "chart"]


class Source(BaseModel):
    title: str
    url: str
    kind: Literal["primary", "secondary"] = "secondary"


class Claim(BaseModel):
    id: str
    text: str
    sources: list[Source] = []
    confidence: str = ""


class Component(BaseModel):
    id: str
    kind: str = "node"
    label: str


class Step(BaseModel):
    n: int
    text: str
    components: list[str] = []


class SystemModel(BaseModel):
    components: list[Component] = []
    links: list[list[str]] = []
    steps: list[Step] = []


class Facts(BaseModel):
    arrangement: str = Field(description="The one concrete setup the video depicts")
    claims: list[Claim]
    model: SystemModel = SystemModel()
    open_questions: list[str] = []


class Treatment(BaseModel):
    name: str
    shape: str
    engagement: str = ""
    teaching_fit: str = ""
    accuracy_risk: str = ""
    feasibility: str = ""
    verdict: str = ""


class Decision(BaseModel):
    key: str
    choice: str
    reason: str
    tier: Tier = "hypothesis"
    overridden: bool = False


class SceneOutline(BaseModel):
    title: str
    treatment: str
    seconds: float
    purpose: str = ""


class Dropoff(BaseModel):
    where: str
    why: str
    countermeasure: str


class Strategy(BaseModel):
    audience_profile: str
    learning_objective: str
    creative_concept: str
    treatments: list[Treatment]
    chosen: str
    hook: str
    narrative_structure: str
    visual_direction: str
    narration_approach: str
    scene_breakdown: list[SceneOutline]
    tools: list[str] = []
    decisions: list[Decision] = []
    dropoff: list[Dropoff] = []
    experiment: str = ""
    recipes_used: list[str] = []
    template: str = ""                 # one template for the whole video (design.TEMPLATES)
    template_reason: str = ""


class Sentence(BaseModel):
    text: str
    claims: list[str] = []


class ScriptScene(BaseModel):
    id: str
    title: str
    sentences: list[Sentence]
    terms: list[str] = []


class Script(BaseModel):
    scenes: list[ScriptScene]


class SceneSpec(BaseModel):
    model_config = {"extra": "allow"}
    id: str
    title: str = ""
    treatment: str = "flow2d"
    objective: str = ""
    heading: Optional[str] = None
    elements: list[dict[str, Any]] = []
    links: Optional[list[Union[list[str], dict[str, Any]]]] = None   # [from, to] or {"from", "to", "dashed", "tone", ...}
    cues: list[dict[str, Any]] = []
    lines: Optional[list[dict[str, Any]]] = None
    code: Optional[list[str]] = None
    ui: Optional[dict[str, Any]] = None
    data: Optional[list[dict[str, Any]]] = None
    camera: dict[str, Any] = {}
    pad_start: float = 0.4
    pad_end: float = 0.5
    motion_scale: float = 1.0
    reason: str = ""
    tier: Tier = "hypothesis"
    recipes: list[str] = []


class Storyboard(BaseModel):
    scenes: list[SceneSpec]


class Review(BaseModel):
    passed: bool
    accuracy_issues: list[str] = []
    engagement_notes: list[str] = []
    summary: str = ""
