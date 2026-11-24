"""CDN Reel v3: footage opening + a continuous camera journey (space -> Europe -> Asia -> building -> rack), then the
approved scenes. Writes script_v3.json and board_v3.json next to this file."""
import json
from pathlib import Path

H = Path(__file__).parent
VA = {"lat": 38.9, "lon": -77.4}

# CloudFront edge locations (POP cities) published on https://aws.amazon.com/cloudfront/features/ (read 2026-11-24).
# Only cities that the page lists and Natural Earth can place are plotted (Dusseldorf is listed but not placeable).
EU_POPS = ["London", "Manchester", "Dublin", "Paris", "Marseille", "Amsterdam", "Brussels", "Frankfurt", "Hamburg", "Berlin",
           "Munich", "Zurich", "Milan", "Rome", "Vienna", "Prague", "Warsaw", "Budapest", "Zagreb", "Sofia", "Bucharest",
           "Athens", "Madrid", "Barcelona", "Lisbon", "København", "Oslo", "Stockholm", "Helsinki"]
ASIA_POPS = ["Seoul", "Tokyo", "Osaka", "Taipei"]

script = {"scenes": [
    {"id": "s1", "title": "Press play", "sentences": [{"text": "You press play on Netflix in London.", "claims": ["c6"]}], "terms": []},
    {"id": "s2", "title": "One distant origin", "sentences": [
        {"text": "It starts instantly. Why?", "claims": ["c6"]},
        {"text": "Without a CDN, the video lives on one origin in us-east-1.", "claims": ["c1"]},
        {"text": "London, Frankfurt and Seoul all wait on it.", "claims": ["c1"]}], "terms": ["CDN"]},
    {"id": "s3", "title": "Copies near viewers", "sentences": [
        {"text": "A CDN keeps copies of popular content near viewers.", "claims": ["c2", "c3"]},
        {"text": "CloudFront runs more than 750 points of presence.", "claims": ["c5"]}], "terms": ["point of presence"]},
    {"id": "s4", "title": "Across the world", "sentences": [
        {"text": "Over 50 countries, from London and Frankfurt to Seoul and Tokyo.", "claims": ["c5", "c12"]}], "terms": []},
    {"id": "s5", "title": "Netflix Open Connect", "sentences": [
        {"text": "Netflix runs its own CDN, called Open Connect.", "claims": ["c6"]}], "terms": ["Open Connect"]},
    {"id": "s6", "title": "Inside your ISP", "sentences": [
        {"text": "Its servers sit inside internet providers and at exchange points, pre-filled by region.", "claims": ["c6", "c7", "c8"]}], "terms": []},
]}
old = json.loads((H / "script.json").read_text(encoding="utf-8"))
script["scenes"] += [s for s in old["scenes"] if s["id"] in ("s7", "s8", "s9", "s10")]
for sc in script["scenes"]:                       # the ending echoes the opening ("London")
    for x in sc["sentences"]:
        if x["text"] == "It starts fast: the video was already near you.":
            x["text"] = "It starts fast in London: the video was already near you."

reg = lambda place, code, side="right", at=None, **kw: dict({"place": place, "kind": "region", "label": place, "code": code, "side": side}, **({"at": at} if at else {"at_frac": 0.02}), **kw)
edges = lambda names, a, b: [{"place": n, "kind": "edge", "at_frac": round(a + (b - a) * i / max(1, len(names) - 1), 3)} for i, n in enumerate(names)]
pulse = lambda *words: [{"at": {"word": w}, "action": "pulse"} for w in words]

scenes = [
 {"id": "s1", "title": "Press play", "treatment": "footage", "src": "cdn-opening-9x16.mp4",
  "align": {"word": "play", "beat": "play_pressed"}, "transition": "cut",
  "objective": "Hook: the viewer presses play", "reason": "The channel owner's opening clip, played as-is with its own sound.", "tier": "hypothesis", "recipes": []},

 {"id": "s2", "title": "One distant origin", "treatment": "motion", "effect": "globe", "transition": "cut",
  "from_point": {"bg": [5, 12, 26], "point": [56, 214, 255], "fade": 0.6}, "cy_px": 960, "drift": 0.0,
  "headline": "It starts instantly. Why?", "headline_at": {"word": "starts"}, "headline_until": {"word": "Without"},
  "fly": [{"place": "London", "zoom": 14.0},
          {"place": "London", "zoom": 1.35, "at": 0.05, "fly": 2.2},
          {"lat": 44, "lon": -36, "zoom": 1.1, "at": {"word": "Without"}, "fly": 1.6},
          {"lat": 60, "lon": 30, "zoom": 0.95, "at": {"word": "Seoul"}, "fly": 1.4},
          {"lat": 50, "lon": 8, "zoom": 2.6, "at_end": 1.0, "fly": 1.0}],
  "cities": [{"place": "London", "at": 0.0, "side": "left"},
             dict(VA, kind="region", label="N. Virginia", code="us-east-1", side="left", at={"word": "origin"}),
             {"place": "Frankfurt", "at": {"word": "Frankfurt"}}, {"place": "Seoul", "at": {"word": "Seoul"}, "side": "left"}],
  "arcs": [{"from": VA, "to": "London", "at": {"word": "London"}, "tone": "fail"},
           {"from": VA, "to": "Frankfurt", "at": {"word": "Frankfurt"}, "tone": "fail", "width": 4},
           {"from": VA, "to": "Seoul", "at": {"word": "Seoul"}, "tone": "fail", "width": 4, "dur": 1.6}],
  "cues": pulse("starts", "Without", "origin", "wait"),
  "objective": "Wide space shot: one distant origin", "tier": "hypothesis", "recipes": [],
  "reason": "Continues from the clip's final frame (navy, cyan point = London), pulls out to the real night Earth; us-east-1 glows and long arcs show the problem."},

 {"id": "s3", "title": "Copies near viewers", "treatment": "motion", "effect": "flat_map", "transition": "crossfade",
  "fly": [{"lat": 48, "lon": 8, "span": 46}, {"lat": 48.5, "lon": 9, "span": 38, "at": 0.3, "fly": 7.0}],
  "cities": [reg("London", "eu-west-2", "left"), reg("Frankfurt", "eu-central-1", "right")] + edges(EU_POPS, 0.05, 0.62),
  "legend": [{"mark": "region", "label": "AWS Region"}, {"mark": "edge", "label": "CloudFront edge location"}],
  "counter": {"value": 750, "suffix": "+", "label": "CloudFront points of presence", "source": "aws.amazon.com/cloudfront/features", "at": {"word": "750"}},
  "cues": pulse("copies", "viewers", "750"),
  "objective": "Regional map: edge locations light up across Europe while the sourced count runs up", "tier": "hypothesis", "recipes": [],
  "reason": "Dive from space into Europe: Regions as large rings with codes, edge locations as small points; counter from the first frame (no empty start)."},

 {"id": "s4", "title": "Across the world", "treatment": "motion", "effect": "flat_map", "transition": "crossfade",
  "fly": [{"lat": 48.5, "lon": 9, "span": 38}, {"lat": 42, "lon": 72, "span": 70, "at": {"word": "to"}, "fly": 1.3},
          {"lat": 36.5, "lon": 132, "span": 17, "at": {"word": "Seoul"}, "fly": 1.2},
          {"place": "Seoul", "span": 9, "at_end": 0.7, "fly": 0.7}],
  "cities": [reg("London", "eu-west-2", "left"), reg("Frankfurt", "eu-central-1", "right"),
             reg("Seoul", "ap-northeast-2", "left", {"word": "Seoul"}), reg("Tokyo", "ap-northeast-1", "right", {"word": "Tokyo"})]
            + edges(ASIA_POPS, 0.35, 0.6) + edges(EU_POPS[:10], 0.0, 0.05),
  "legend": [{"mark": "region", "label": "AWS Region"}, {"mark": "edge", "label": "CloudFront edge location"}],
  "cues": pulse("countries", "Seoul", "Tokyo"),
  "objective": "City close-up: pan to Asia, Seoul and Tokyo with their edge points, then dive into Seoul", "tier": "hypothesis", "recipes": [],
  "reason": "Continuous camera from Europe to North-East Asia; ends on a close-up of one city."},

 {"id": "s5", "title": "Netflix Open Connect", "treatment": "motion", "effect": "model_3d", "model": "datacenter", "transition": "crossfade",
  "headline": "Netflix runs its own CDN", "label": "An ISP's data centre", "sub": "Seoul (example)", "start": 0.45, "scale": 1.25,
  "zoom_in": {"from": 0.45, "dur": 1.1}, "push_out": {"at_end": 0.8, "to": 2.8},
  "cues": pulse("Netflix", "Connect"),
  "objective": "Building: zoom from the city into an ISP site", "tier": "hypothesis", "recipes": [],
  "reason": "The camera keeps moving forward: city close-up, the building, then into it."},

 {"id": "s6", "title": "Inside your ISP", "treatment": "motion", "effect": "model_3d", "model": "server_rack", "transition": "crossfade",
  "headline": "Open Connect", "label": "Open Connect Appliance", "sub": "inside ISP networks and at exchange points",
  "zoom_in": {"from": 0.5, "dur": 1.0},
  "cues": pulse("providers", "exchange", "pre-filled"),
  "objective": "Rack: the appliance inside the ISP", "tier": "hypothesis", "recipes": [],
  "reason": "Inside the building: the Open Connect Appliance rack."},
]
oldb = json.loads((H / "board.json").read_text(encoding="utf-8"))
scenes += [s for s in oldb["scenes"] if s["id"] in ("s7", "s8", "s9", "s10")]
for s in scenes:
    if s["treatment"] != "footage":
        s.setdefault("pad_end", 0.15)
(H / "script_v3.json").write_text(json.dumps(script, ensure_ascii=False, indent=1), encoding="utf-8")
(H / "board_v3.json").write_text(json.dumps({"scenes": scenes}, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(scenes), "scenes;", sum(len(x["text"].split()) for sc in script["scenes"] for x in sc["sentences"]), "words")
