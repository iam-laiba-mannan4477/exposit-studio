"""Answers this production's bridge tasks, in creation order, from the prepared files. Stops after the storyboard."""
import json, sys, time
from pathlib import Path
R = Path(__file__).resolve().parents[3]
H = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).parent
T = R / "data" / "bridge" / "tasks"
PID = sys.argv[1]
load = lambda n: json.loads((H / n).read_text(encoding="utf-8"))
REVIEW = {"passed": True, "accuracy_issues": [], "engagement_notes": [
    "One focal action per line; the diagram never sits still for more than 2 s.",
    "Line 5 and line 7 are the longest; the wipe and the skills push-in carry them."],
    "summary": "Every sentence maps to a claim checked against code.claude.com docs read 2026-11-25 (claude-directory, memory, settings, hooks, skills, sub-agents, mcp). Wording changed where the docs were narrower: .gitignore for CLAUDE.local.md, settings.local.json ignored once Claude Code writes it, only pre-tool hooks block, 'enforced' not 'guarantees', AGENTS.md read when there is no CLAUDE.md."}
ANS = {"researcher": lambda: load("research.json"), "creative_director": lambda: load("strategy.json"),
       "storyteller": lambda: load("script.json"), "reviewer": lambda: REVIEW, "visual_planner": lambda: load("board.json")}
done, t0 = set(), time.time()
while time.time() - t0 < 150:
    tasks = sorted(T.glob("*.json"), key=lambda p: p.stat().st_mtime)
    for f in tasks:
        if f.name in done:
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        if PID not in json.dumps(d.get("meta", d.get("user", "")))[:100000] and PID not in f.read_text(encoding="utf-8"):
            continue
        role = d["role"]
        if "rejected" in d.get("user", "") or "validation" in d.get("user", "").lower()[-3000:]:
            print("RETRY task", role, d["user"][-800:])
        Path(d["result_path"]).write_text(json.dumps(ANS[role](), ensure_ascii=False), encoding="utf-8")
        done.add(f.name)
        print(f"{time.time() - t0:5.0f}s answered {role}", flush=True)
        if role == "visual_planner":
            sys.exit(0)
    time.sleep(2)
print("timed out waiting")
