"""TechHub Reel: "How do you ship a 212 GB game to millions at midnight?" (the DevOps behind the GTA 6 launch).
Publicly reported facts only (checked 2026-11-27); general techniques framed as how a launch like this works.
No game art, no logos. Template midnight-launch; two Blender shots (S3 network3d, S5 globe3d).
Writes script.json, board.json, research.json and strategy.json next to this file."""
import json, sys
from pathlib import Path

H = Path(__file__).parent
R = H.parents[2]
sys.path.insert(0, str(R))

S = lambda text, *claims: {"text": text, "claims": list(claims)}
LINES = [
 ("s1", "212 GB at midnight", [S("GTA 6 needs up to two hundred and twelve gigabytes, and Take-Two reported over thirty-two million copies sold before release.", "c1", "c10"),
                               S("So how do you ship that without breaking the internet?", "c3")]),
 ("s2", "Preload window", [S("Step one: preloads opened over a week early, so the bytes could move before launch day.", "c2")]),
 ("s3", "CDN", [S("Downloads like this come from C D Ns: copies cached on edge servers near players.", "c9")]),
 ("s4", "Comcast record", [S("Comcast said the first forty-eight hours of preloads were the largest single event in its network history.", "c4")]),
 ("s5", "Rolling midnight", [S("Step two: stagger the spike.", "c3"),
                             S("The game unlocked at midnight local time, rolling around the planet from New Zealand.", "c3")]),
 ("s6", "Deltas", [S("Step three: ship deltas.", "c5"), S("The first patch was about one gigabyte on PS5, not another two hundred.", "c5")]),
 ("s7", "Licence check", [S("One thing can't be preloaded: the licence check.", "c7"),
                          S("Hours before launch, PlayStation Network struggled, and a downloaded game can still need that check to start.", "c6", "c7")]),
 ("s8", "The lesson", [S("The lesson: move the bytes early, stagger the spike, and find the one dependency everyone hits at once.", "c2", "c3", "c7")]),
 ("s9", "Pipeline", [S("Here's the whole launch pipeline.", "c8"), S("Save it for your next release plan.", "c8")]),
]
script = {"scenes": [{"id": i, "title": t, "sentences": s, "terms": []} for i, t, s in LINES]}

w = lambda x, off=0.0, occ=1: {"word": x, "offset": off, "occurrence": occ}
ML = {"bg": "#0D0B1A", "base": "#26204A", "accent": "#FF8A3D", "glow": "#3DD6D0", "rim": "#FF4F9A", "text": "#F4F1EA"}
SC = {
 "s1": dict(kind="ml_hook", tout="zoom", focus_out=[540, 1290], sold_at=w("Take-Two"),
            pops=[{"text": "Without breaking the internet?", "at": w("breaking"), "y": 1470, "size": 60, "hold": 1.6}],
            cues=[{"at": 0.1, "action": "type"}, {"at": w("Take-Two"), "action": "highlight"}, {"at": w("release.", 0.1), "action": "type"}, {"at": w("release.", 0.7), "action": "thud"},
                  {"at": w("breaking"), "action": "highlight"}],
            objective="212 GB counts up; console dots light across a dark map; 00:00; every dot fires at one server, which turns red and shakes"),
 "s2": dict(kind="ml_preload", tin="zoom", focus_in=[540, 900], tout="push",
            pops=[{"text": "Over a week early", "at": w("early,"), "y": 300, "size": 56}],
            cues=[{"at": 0.0, "action": "whoosh_soft"}, {"at": w("preloads"), "action": "packet"}, {"at": w("early,"), "action": "highlight"},
                  {"at": w("launch"), "action": "packet"}],
            objective="A Nov 10-19 preload window fills day by day; a midnight spike vs the same bytes spread over the window"),
 "s3": dict(treatment="blender3d", shot="network3d", transition="push", palette=ML,
            params={"nodes": [{"name": "origin", "pos": [0, 0, 1.0]}, {"name": "e1", "pos": [-2.6, 1.4, 0.6]},
                              {"name": "e2", "pos": [2.6, 1.4, 0.6]}, {"name": "e3", "pos": [-2.2, -1.8, 0.6]}, {"name": "e4", "pos": [2.2, -1.8, 0.6]}],
                    "links": [["origin", "e1"], ["origin", "e2"], ["origin", "e3"], ["origin", "e4"]], "leaves": 3},
            camera={"orbit": 18, "dolly": 1.0, "distance": 8.6, "elevation": 48, "target": [0, 0, 0.6]},
            labels=[{"text": "origin", "anchor": "origin", "at": 0.3, "dy": -70, "size": 40},
                    {"text": "edge cache", "anchor": "e2", "at": w("edge"), "dy": -60},
                    {"text": "edge cache", "anchor": "e3", "at": w("edge", 0.3), "dy": -60},
                    {"text": "players nearby", "anchor": "e4", "at": w("players"), "dy": 70}],
            cues=[{"at": w("Downloads"), "action": "packet"}, {"at": w("edge"), "action": "highlight"}, {"at": w("copies"), "action": "highlight"}],
            objective="Blender: one origin, edge caches around it, then short local hops to players"),
 "s4": dict(kind="ml_comcast", rev=2, tin="whip", wipe_out=True,
            cues=[{"at": 0.0, "action": "whoosh_soft"}, {"at": w("forty-eight"), "action": "packet"}, {"at": w("largest"), "action": "highlight"}],
            objective="A traffic line climbs off the top of the chart; 'largest single event in its network history' (Comcast)"),
 "s5": dict(treatment="blender3d", shot="globe3d", transition="cut", palette=ML,
            params={"texture": str(R / "exposit" / "assets" / "earth" / "day-4096.jpg"), "spin": 70,
                    "sweep": {"start_lon": 175, "turn": 330, "width": 10, "lon_facing_at_zero": -80, "opacity": 0.35}},
            camera={"orbit": 0, "dolly": 0.6, "distance": 8.5, "elevation": 12, "target": [0, 0, 1.2]},
            labels=[{"text": "Stagger the spike", "x": 0.5, "y": 0.2, "size": 56, "at": w("stagger")},
                    {"text": "New Zealand", "x": 0.1, "y": 0.78, "progress": 0.0},
                    {"text": "Australia", "x": 0.1, "y": 0.78, "progress": 0.076},
                    {"text": "Japan", "x": 0.1, "y": 0.78, "progress": 0.11},
                    {"text": "Europe", "x": 0.1, "y": 0.78, "progress": 0.48},
                    {"text": "Americas", "x": 0.1, "y": 0.78, "progress": 0.76}], latest_only=True,
            cues=[{"at": w("stagger"), "action": "highlight"}, {"at": w("midnight"), "action": "type"}, {"at": w("Zealand."), "action": "highlight"}],
            cover=True,
            objective="Blender globe: an orange local-midnight band sweeps west from New Zealand; regions light in turn"),
 "s6": dict(kind="ml_delta", tin="mask", focus_in=[540, 900], tout="push",
            pops=[{"text": "Ship deltas", "at": w("deltas."), "y": 300, "size": 60}],
            cues=[{"at": 0.0, "action": "whoosh_soft"}, {"at": w("deltas."), "action": "highlight"}, {"at": w("patch"), "action": "packet"},
                  {"at": w("another"), "action": "highlight"}],
            objective="A 212 GB block of chunks; only the changed chunks glow and ship as a 1.07 GB patch"),
 "s7": dict(kind="ml_licence", tin="push", tout="whip", shake_at=w("struggled,"),
            cues=[{"at": 0.0, "action": "whoosh_soft"}, {"at": w("licence"), "action": "highlight"}, {"at": w("struggled,"), "action": "thud"},
                  {"at": w("start."), "action": "highlight"}],
            objective="A fully downloaded console waits at the licence gate while PSN is disrupted; offline play is the exception"),
 "s8": dict(kind="ml_lesson", tin="whip", wipe_out=True,
            cues=[{"at": w("early,"), "action": "highlight"}, {"at": w("spike,"), "action": "highlight"}, {"at": w("dependency"), "action": "thud"},
                  {"at": w("once."), "action": "highlight"}],
            objective="Three numbered lessons; card 3 links back to the red licence gate"),
 "s9": dict(kind="ml_pipeline", wipe_in=True, pad_end=1.6,
            cues=[{"at": 0.0, "action": "whoosh_soft"}, {"at": w("pipeline."), "action": "highlight"}, {"at": w("plan."), "action": "soft"},
                  {"at": w("plan.", 0.9), "action": "whoosh_soft"}],
            objective="Save-worthy pipeline: build & release, origin, CDN edges, preload window, rolling unlock, licence check (single point of failure), player"),
}
scenes = []
for s in script["scenes"]:
    sp = {"id": s["id"], "title": s["title"], "treatment": "motion", "effect": "dev_scene", "transition": "cut",
          "pad_start": 0.1, "pad_end": 0.15, "tier": "hypothesis", "recipes": [], "reason": "A different layout per line; the picture follows the words."}
    sp.update(SC[s["id"]])
    if sp["treatment"] == "blender3d":
        sp.pop("effect", None)
        sp.setdefault("fallback", None)
        sp.pop("fallback")
    if s["id"] == "s1":
        sp["transition"] = "fade"
    scenes.append(sp)

src = lambda title, url, kind="primary": {"title": f"{title} (read 2026-11-27)", "url": url, "kind": kind}
claims = [
 ("c10", "Take-Two's SEC filing (Form 8-K, Exhibit 99.1, 20 November 2026) reported 32.5 million GTA VI units sold pre-release. Sensor Tower had estimated about 17.1 million by midday on 18 November (Reuters).",
  [src("Take-Two Form 8-K, Exhibit 99.1 (SEC)", "https://www.sec.gov/Archives/edgar/data/946581/000162828026075217/exhibit9918k.htm"),
   src("Reuters via Fox 5 NY: Sensor Tower estimate", "https://www.fox5ny.com/news/gta-vi-pulls-estimated-1-84-billion-release-day-more-than-double-gta-vs-launch-record", "secondary"),
   src("Forbes Australia: GTA VI pre-launch revenue", "https://www.forbes.com.au/news/innovation/gta-vi-has-already-banked-1-5-billion-and-it-isnt-out-yet/", "secondary")]),
 ("c1", "Rockstar says the GTA VI pre-load requires up to 212 GB of free space depending on the device; measured PS5 downloads were about 209.8 GB.",
  [src("Rockstar Newswire: Pre-Load Grand Theft Auto VI Now", "https://www.rockstargames.com/newswire/article/89834o94713o21/pre-load-grand-theft-auto-vi-now"),
   src("VICE: How big is GTA 6 on PS5", "https://www.vice.com/en/article/gta-6-download-size-ps5/", "secondary")]),
 ("c2", "Pre-loading opened on 10 November 2026 (moved forward from 12 November), nine days before the 19 November launch.",
  [src("Rockstar Newswire: GTA VI pre-load begins on November 10", "https://www.rockstargames.com/newswire/article/k4ak9okk485712/grand-theft-auto-vi-pre-load-begins-on-november-10")]),
 ("c3", "GTA VI unlocked at midnight local time on 19 November in each region, starting in New Zealand (11:00 UTC on 18 November).",
  [src("Rockstar Support: regional pre-load and release times", "https://support.rockstargames.com/articles/29jV3Cv2cCgvwM1XgtMO5o/grand-theft-auto-vi-regional-pre-load-and-release-times-on-playstation-5-and-xbox-series-x-or-s"),
   src("PC Gamer: GTA 6 release times", "https://www.pcgamer.com/games/grand-theft-auto/gta-6-release-time-date/", "secondary")]),
 ("c4", "Comcast's Chief Network Officer said the first 48 hours of GTA VI pre-loads were the largest single event in Comcast's network history.",
  [src("Newsweek: GTA 6 could break traffic records", "https://www.newsweek.com/entertainment/gta-6-internet-traffic-records-12726270", "secondary")]),
 ("c5", "Patch 01.002.000 (13 November) was about 1.07 GB on PS5.",
  [src("Red Bull: GTA 6 launch updates and patch sizes", "https://www.redbull.com/int-en/gta-6-updates-patch-notes", "secondary")]),
 ("c6", "On 18 November, hours before the unlock, PlayStation Network's status page showed sign-in, Store and gaming service problems; Sony gave no cause.",
  [src("IBTimes UK: PlayStation Network outage hours before GTA 6 launch", "https://www.ibtimes.co.uk/psn-sign-problems-before-gta-6-release-1833247", "secondary")]),
 ("c7", "PS5 digital games are licensed to the PSN account; Console Sharing and Offline Play lets the primary console play them offline, though some content may need online revalidation.",
  [src("PlayStation Support: PS5 Console Sharing and Offline Play", "https://www.playstation.com/en-us/support/account/ps5-console-sharing-offline-play/")]),
 ("c8", "Rockstar hires Build & Release Engineers to automate builds and deployment; postings mention TeamCity or Jenkins and Perforce.",
  [src("Rockstar Games careers (Greenhouse): Build & Release Engineer", "https://job-boards.greenhouse.io/rockstargames/jobs/6269117003")]),
 ("c9", "Large game downloads are served through content delivery networks that cache copies on edge servers near players (general technique, not a statement about Rockstar's systems).",
  [src("Cloudflare: What is a CDN?", "https://www.cloudflare.com/learning/cdn/what-is-a-cdn/")]),
]
research = {"arrangement": "A large console game launch: build and release, origin storage, CDN edges, a pre-load window, a rolling midnight unlock, and a licence check at start (how a launch like this works; not Rockstar's internal architecture).",
            "claims": [{"id": i, "text": t, "sources": s, "confidence": "high" if any(x["kind"] == "primary" for x in s) else "medium"} for i, t, s in claims],
            "model": {"components": [{"id": "build", "kind": "service", "label": "Build & release"}, {"id": "origin", "kind": "service", "label": "Origin"},
                                     {"id": "cdn", "kind": "zone", "label": "CDN edges"}, {"id": "lic", "kind": "service", "label": "Licence check"},
                                     {"id": "player", "kind": "browser", "label": "Player"}],
                      "links": [["build", "origin"], ["origin", "cdn"], ["cdn", "player"], ["player", "lic"]],
                      "steps": [{"n": 1, "text": "Builds are published to an origin.", "components": ["build", "origin"]},
                                {"n": 2, "text": "CDN edges cache copies near players during the pre-load window.", "components": ["origin", "cdn", "player"]},
                                {"n": 3, "text": "At local midnight the game unlocks; starting it needs a licence check.", "components": ["player", "lic"]}]},
            "open_questions": []}
strategy = {
 "audience_profile": "Senior engineers who ship releases and want to see how a very large launch avoids one traffic spike.",
 "learning_objective": "Three launch techniques (pre-load, staggered unlock, deltas) and the one dependency that cannot be pre-loaded.",
 "creative_concept": "A launch-control room in neon lines: one story from 212 GB to the single point of failure, ending on a save-worthy pipeline.",
 "treatments": [{"name": "A. Launch-control diagrams with two 3D shots", "shape": "counter + map, timeline, CDN network (3D), traffic graph, rolling globe (3D), chunk grid, gate, cards, pipeline",
                 "engagement": "high", "teaching_fit": "strong", "accuracy_risk": "low: public facts only", "feasibility": "dev_scene + blender3d", "verdict": "Chosen."},
                {"name": "B. Talking points over stock footage", "shape": "b-roll", "engagement": "medium", "teaching_fit": "weak", "accuracy_risk": "IP risk", "feasibility": "no footage", "verdict": "Rejected: no game art allowed."},
                {"name": "C. One long diagram", "shape": "single pipeline built step by step", "engagement": "medium", "teaching_fit": "good", "accuracy_risk": "low", "feasibility": "easy", "verdict": "Rejected: one layout for 60 s."}],
 "chosen": "A. Launch-control diagrams with two 3D shots",
 "hook": "212 GB counts up; at 00:00 every console fires at one server.",
 "narrative_structure": "The problem; three techniques; the dependency that can't be pre-loaded; the lesson; the pipeline to save.",
 "visual_direction": "midnight-launch: night navy-purple, orange, pink and teal neon lines; no game art, no logos.",
 "narration_approach": "Calm and precise; numbers spoken naturally; PS5 as 'P S five'.",
 "scene_breakdown": [{"title": sp["title"], "treatment": sp["treatment"], "effect": sp.get("shot") or ("dev_scene:" + sp.get("kind", "")),
                      "seconds": 6.5, "purpose": sp["objective"]} for sp in scenes],
 "tools": ["Exposit renderer", "Kokoro voice", "Blender (optional 3D)", "Lucide icons"],
 "decisions": [{"key": "template", "choice": "midnight-launch", "reason": "User's choice; an original control-room look, not the game's style.", "tier": "preference"},
               {"key": "3d", "choice": "two Blender shots: CDN network, rolling-midnight globe", "reason": "Depth explains distribution and time zones.", "tier": "preference"},
               {"key": "honesty", "choice": "public facts only; techniques framed generally", "reason": "Rockstar has not published its infrastructure.", "tier": "preference"},
               {"key": "ip", "choice": "no game art, logos or footage", "reason": "User rule.", "tier": "preference"},
               {"key": "transitions", "choice": "zoom-through, push, whip, wipes, mask", "reason": "A different transition on every cut.", "tier": "preference"}],
 "dropoff": [{"where": "s7 licence check", "why": "Abstract", "countermeasure": "A console visibly waits at a red gate"}],
 "experiment": "Does a news hook framed as an engineering question hold senior viewers?", "recipes_used": [],
 "template": "midnight-launch", "template_reason": "User's choice for this video.",
 "effects": ["dev_scene"], "effects_reason": "2D diagrams (dev_scene) for most lines; two blender3d shots (a treatment, not a motion effect) where depth explains."}
for name, obj in (("script", script), ("board", {"scenes": scenes}), ("research", research), ("strategy", strategy)):
    (H / f"{name}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(scenes), "scenes;", sum(len(x["text"].split()) for sc in script["scenes"] for x in sc["sentences"]), "words")
