"""Creative intelligence library and capability registry. Seeded from files; changed only through the API."""
from __future__ import annotations
import json
from . import config, store

TIERS = ["verified", "preference", "observation", "hypothesis", "experiment"]
TIER_RANK = {t: i for i, t in enumerate(TIERS)}


def seed() -> None:
    if not store.q("SELECT id FROM knowledge LIMIT 1"):
        for it in json.loads((config.SEEDS / "knowledge.json").read_text(encoding="utf-8")):
            add_item(it)
    if not store.q("SELECT id FROM registry LIMIT 1"):
        for r in json.loads((config.SEEDS / "registry.json").read_text(encoding="utf-8")):
            upsert_tool(r)


def add_item(it: dict) -> dict:
    it = dict(it)
    it.setdefault("id", store.new_id("k"))
    it.setdefault("status", "active")
    extra = {k: v for k, v in it.items() if k not in ("id", "kind", "title", "body", "category", "tier", "source", "date", "applies", "confidence", "status")}
    store.q("INSERT OR REPLACE INTO knowledge VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (it["id"], it.get("kind", "recipe"), it.get("title", ""), it.get("body", ""), it.get("category", ""), it.get("tier", "hypothesis"),
             it.get("source", ""), it.get("date", ""), it.get("applies", ""), it.get("confidence", ""), it["status"], store.jdump(extra)))
    return it


def _row(r: dict) -> dict:
    d = json.loads(r.pop("data") or "{}")
    r.update(d)
    return r


def items(category: str = "", tier: str = "") -> list[dict]:
    rows = [_row(r) for r in store.q("SELECT * FROM knowledge ORDER BY category, title")]
    return [r for r in rows if (not category or r["category"] == category) and (not tier or r["tier"] == tier)]


def for_strategy(limit: int = 40) -> list[dict]:
    """Active items for the Creative Director, strongest evidence first."""
    rows = [r for r in items() if r["status"] == "active"]
    rows.sort(key=lambda r: TIER_RANK.get(r["tier"], 9))
    return [{k: r[k] for k in ("id", "category", "title", "body", "tier", "applies", "confidence")} for r in rows[:limit]]


def note_usage(ids: list[str], production_id: str) -> None:
    for r in store.q("SELECT id,data FROM knowledge"):
        if r["id"] in ids:
            d = json.loads(r["data"] or "{}")
            used = d.setdefault("used_in", [])
            if production_id not in used:
                used.append(production_id)
            store.q("UPDATE knowledge SET data=? WHERE id=?", (store.jdump(d), r["id"]))


def upsert_tool(t: dict) -> dict:
    t = dict(t)
    t.setdefault("id", store.new_id("r"))
    extra = {k: v for k, v in t.items() if k not in ("id", "name", "url", "category", "licence", "maintenance", "cost", "hardware", "status")}
    store.q("INSERT OR REPLACE INTO registry VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (t["id"], t.get("name", ""), t.get("url", ""), t.get("category", ""), t.get("licence", "unknown"), t.get("maintenance", ""),
             t.get("cost", ""), t.get("hardware", ""), t.get("status", "discovered"), store.now(), store.jdump(extra)))
    return t


def tools() -> list[dict]:
    return [_row(r) for r in store.q("SELECT * FROM registry ORDER BY status, name")]


def set_tool_status(tid: str, status: str) -> None:
    store.q("UPDATE registry SET status=?, updated=? WHERE id=?", (status, store.now(), tid))
