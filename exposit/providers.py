"""Model providers. The Director never depends on one vendor: every role call goes through complete().

bridge      - writes a task file and waits for any coding agent (or a person) to write the result. No API cost.
claude_cli  - runs the Claude Code CLI without a window. Uses your existing plan and its limits.
openai      - any OpenAI-compatible endpoint: Ollama, LM Studio, a hosted provider. Key from EXPOSIT_LLM_API_KEY.
anthropic   - the Anthropic Messages API. Key from EXPOSIT_LLM_API_KEY. Paid.
"""
from __future__ import annotations
import json, shutil, subprocess, time
from pathlib import Path
import httpx
from . import config, store


class ProviderError(RuntimeError):
    pass


LOCAL_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0", "host.docker.internal")


def is_paid(s: dict) -> bool:
    p = s.get("llm_provider")
    if p == "anthropic":
        return True
    if p == "openai":
        return not any(h in (s.get("llm_base_url") or "") for h in LOCAL_HOSTS)
    return False


def status() -> dict:
    s = store.get_settings()
    p = s.get("llm_provider", "bridge")
    info = {"provider": p, "paid": is_paid(s), "ready": True, "note": ""}
    if p == "none":
        info.update(ready=False, note="No AI provider selected. Choose one in Settings.")
    elif p == "claude_cli":
        ok = shutil.which(config.env("EXPOSIT_CLAUDE_BIN", "claude")) is not None
        info.update(ready=ok, note="Uses your Claude Code plan and its limits." if ok else "The 'claude' command was not found on PATH.")
    elif p in ("openai", "anthropic"):
        if not s.get("llm_model"):
            info.update(ready=False, note="Set a model name in Settings.")
        elif info["paid"] and not config.env("EXPOSIT_LLM_API_KEY"):
            info.update(ready=False, note="Set EXPOSIT_LLM_API_KEY in .env.")
        elif info["paid"] and float(s.get("budget_paid_usd") or 0) <= 0:
            info.update(ready=False, note="This provider is paid and the budget for paid services is $0. Raise the budget in Settings to allow it.")
    elif p == "bridge":
        info.update(note="Tasks wait in data/bridge/tasks until a coding agent or you answer them. No API cost.")
    return info


def bridge_dir() -> Path:
    return config.DATA / "bridge"


def bridge_pending() -> list[dict]:
    out = []
    for f in sorted((bridge_dir() / "tasks").glob("*.json")):
        try:
            t = json.loads(f.read_text(encoding="utf-8"))
            out.append({k: t.get(k) for k in ("id", "role", "created", "production_id", "result_path")})
        except Exception:
            pass
    return out


def bridge_submit(task_id: str, text: str) -> None:
    (bridge_dir() / "results" / f"{task_id}.json").write_text(text, encoding="utf-8")


def _bridge(system: str, user: str, role: str, meta: dict, timeout: float) -> str:
    tid = store.new_id("t")
    task = bridge_dir() / "tasks" / f"{tid}.json"
    result = bridge_dir() / "results" / f"{tid}.json"
    task.write_text(json.dumps({"id": tid, "role": role, "created": time.time(), "system": system, "user": user,
                                "result_path": str(result), **{k: v for k, v in meta.items() if not k.startswith("_")}}, indent=1, ensure_ascii=False), encoding="utf-8")
    cb = meta.get("_on_wait")
    start = time.time()
    while time.time() - start < timeout:
        if result.exists():
            time.sleep(0.2)
            text = result.read_text(encoding="utf-8")
            task.unlink(missing_ok=True)
            result.unlink(missing_ok=True)
            return text
        if cb:
            cb(f"Waiting for the agent: task {tid} ({role}). See data/bridge/tasks.")
        time.sleep(1.0)
    task.unlink(missing_ok=True)
    raise ProviderError(f"No agent answered task {tid} ({role}) within {int(timeout)} s.")


def _claude_cli(system: str, user: str, timeout: float) -> str:
    exe = shutil.which(config.env("EXPOSIT_CLAUDE_BIN", "claude"))
    if not exe:
        raise ProviderError("The 'claude' command was not found. Install Claude Code or pick another provider.")
    r = subprocess.run([exe, "-p", system + "\n\n" + user, "--output-format", "text"], capture_output=True, text=True,
                       timeout=timeout, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise ProviderError("claude exited with an error: " + (r.stderr or r.stdout)[-400:])
    return r.stdout


def _openai(system: str, user: str, s: dict, timeout: float) -> str:
    headers = {"Content-Type": "application/json"}
    key = config.env("EXPOSIT_LLM_API_KEY")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    body = {"model": s["llm_model"], "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.4}
    r = httpx.post(s["llm_base_url"].rstrip("/") + "/chat/completions", headers=headers, json=body, timeout=timeout)
    if r.status_code >= 400:
        raise ProviderError(f"Model endpoint returned {r.status_code}: {r.text[:300]}")
    return r.json()["choices"][0]["message"]["content"]


def _anthropic(system: str, user: str, s: dict, timeout: float) -> str:
    key = config.env("EXPOSIT_LLM_API_KEY")
    r = httpx.post("https://api.anthropic.com/v1/messages", timeout=timeout,
                   headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                   json={"model": s["llm_model"], "max_tokens": 8000, "system": system,
                         "messages": [{"role": "user", "content": user}]})
    if r.status_code >= 400:
        raise ProviderError(f"Anthropic API returned {r.status_code}: {r.text[:300]}")
    return "".join(b.get("text", "") for b in r.json().get("content", []))


def complete(system: str, user: str, role: str = "", meta: dict | None = None) -> str:
    s = store.get_settings()
    st = status()
    if not st["ready"]:
        raise ProviderError(st["note"])
    p = s["llm_provider"]
    timeout = float(config.env("EXPOSIT_LLM_TIMEOUT", "3600" if p == "bridge" else "600"))
    if p == "bridge":
        return _bridge(system, user, role, meta or {}, timeout)
    if p == "claude_cli":
        return _claude_cli(system, user, timeout)
    if p == "openai":
        return _openai(system, user, s, timeout)
    if p == "anthropic":
        return _anthropic(system, user, s, timeout)
    raise ProviderError("No AI provider selected.")
