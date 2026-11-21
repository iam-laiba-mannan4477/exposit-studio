"""Tests run against a throwaway data folder, never the real one."""
import json, os, sys, tempfile, threading, time
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_tmp = tempfile.mkdtemp(prefix="exposit-test-")
os.environ["EXPOSIT_DATA"] = _tmp
os.environ.pop("EXPOSIT_LLM_API_KEY", None)

EX = ROOT / "examples" / "http-request-journey"


def example(name: str) -> dict:
    return json.loads((EX / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from exposit import app as appmod
    with TestClient(appmod.app) as c:      # the context manager runs startup, which starts the single worker
        yield c


def wait_job(client, jid: str, timeout: float = 900) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f"/api/jobs/{jid}").json()
        if j["state"] in ("done", "failed", "cancelled"):
            return j
        time.sleep(0.5)
    raise AssertionError(f"job {jid} did not finish")


_CD_CALLS = [0]                                  # shared across tests, so every production gets a new combination


@pytest.fixture()
def fake_agent():
    """Stands in for a coding agent on the bridge: answers each role's task with the prepared example output."""
    from exposit import providers
    answers = {"researcher": example("facts.json"), "creative_director": example("strategy.json"), "storyteller": example("script.json"),
               "visual_planner": example("board.json"),
               "scene_editor": dict(example("board.json")["scenes"][3], pad_end=1.1), "reviewer": {"passed": True, "accuracy_issues": [], "engagement_notes": [], "summary": "Test reviewer."}}
    seen, stop = [], threading.Event()
    combos = [["focus_frame", "parallax"], ["parallax", "stacking_cards"], ["focus_frame", "line_reveal"], ["parallax", "line_reveal"]]

    def answer(role):
        a = answers[role]
        if role == "creative_director":                     # a new style-and-effects combination each time (variety rule)
            _CD_CALLS[0] += 1
            a = dict(a, effects=combos[_CD_CALLS[0] % len(combos)])
        return a

    def loop():
        while not stop.is_set():
            for t in providers.bridge_pending():
                if t["id"] not in [s[0] for s in seen] and t["role"] in answers:
                    seen.append((t["id"], t["role"]))
                    providers.bridge_submit(t["id"], json.dumps(answer(t["role"])))
            time.sleep(0.2)
    th = threading.Thread(target=loop, daemon=True)
    th.start()
    yield seen
    stop.set()
