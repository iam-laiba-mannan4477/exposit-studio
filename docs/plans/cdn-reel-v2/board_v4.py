"""CDN Reel v4: the user's 8-line script, the picture following the words. Writes script_v4.json, board_v4.json,
research_v4.json next to this file."""
import json
from pathlib import Path

H = Path(__file__).parent
VA = {"lat": 38.9, "lon": -77.4}
EDGES = json.loads((H / "edges_all.json").read_text(encoding="utf-8"))      # every placeable CloudFront edge city
REGIONS = json.loads((H / "regions_all.json").read_text(encoding="utf-8"))  # every AWS Region, at its named place
pulse = lambda *words: [{"at": {"word": w}, "action": "pulse"} for w in words]
layers = {"all_regions": [{"lat": r["lat"], "lon": r["lon"]} for r in REGIONS],
          "all_edges": [{"lat": e["lat"], "lon": e["lon"]} for e in EDGES]}

S = lambda text, *claims: {"text": text, "claims": list(claims)}
script = {"scenes": [
    {"id": "s1", "title": "Press play", "sentences": [S("You press play on Netflix in London,", "c6")], "terms": []},
    {"id": "s2", "title": "The origin", "sentences": [
        S("and the show starts instantly. How?", "c6"),
        S("Every video has a main copy, on an origin server.", "c14"),
        S("Say it sits in a data centre in Virginia.", "c1")], "terms": ["origin server"]},
    {"id": "s3", "title": "One distant place", "sentences": [
        S("Every viewer's request would cross the Atlantic.", "c2"),
        S("That distance adds delay, and millions of requests to one place put a heavy load on it.", "c2", "c15")], "terms": []},
    {"id": "s4", "title": "Copies near viewers", "sentences": [
        S("So copies are kept near viewers.", "c3"),
        S("Like milk: you buy it at the shop down the road, not from the factory.", "c3")], "terms": []},
    {"id": "s5", "title": "The world tour", "sentences": [
        S("Those nearby shops are edge servers.", "c2"),
        S("Together they form a CDN, a content delivery network.", "c2"),
        S("Amazon CloudFront alone has over 750 locations: London, Frankfurt, Mumbai, Singapore, Tokyo, Sydney, Sao Paulo and New York.", "c5", "c13")],
     "terms": ["CDN"]},
    {"id": "s6", "title": "Open Connect", "sentences": [
        S("Netflix built its own, Open Connect, with servers inside your internet provider's network, preloaded with shows for your region.", "c6", "c8")],
     "terms": ["Open Connect"]},
    {"id": "s7", "title": "Hit or miss", "sentences": [
        S("When you press play, the nearby edge checks for a copy.", "c2", "c3"),
        S("Got it? That's a cache hit, sent straight to you.", "c3", "c9"),
        S("Missing? A cache miss: it fetches it from the origin once, and keeps it for the next viewer.", "c4", "c9", "c11")],
     "terms": ["cache hit"]},
    {"id": "s8", "title": "Down the road", "sentences": [
        S("That's why it started instantly.", "c2"),
        S("When you pressed play, nothing crossed an ocean.", "c2"),
        S("The show was already down the road.", "c3", "c8")], "terms": []},
]}

TOUR = ["London", "Frankfurt", "Mumbai", "Singapore", "Tokyo", "Sydney", "Sao Paulo", "New York"]
WORD = {"Sao Paulo": "Sao", "New York": "York"}
fly_tour = [{"lat": 30, "lon": -20, "zoom": 1.0}, {"lat": 30, "lon": 20, "zoom": 1.0, "at": {"word": "edge"}, "fly": 2.0}]
for c in TOUR:
    fly_tour.append({"place": c, "zoom": 1.7, "at": {"word": WORD.get(c, c)}, "fly": 0.6, "lead": 0.4})

scenes = [
 {"id": "s1", "title": "Press play", "treatment": "footage", "src": "cdn-opening-9x16.mp4",
  "align": {"word": "play", "beat": "play_pressed"}, "transition": "cut",
  "objective": "The viewer presses play", "reason": "The channel owner's clip, as-is.", "tier": "hypothesis", "recipes": []},

 {"id": "s2", "title": "The origin", "treatment": "motion", "effect": "globe", "transition": "cut", "labels": "compact",
  "from_point": {"bg": [5, 12, 26], "point": [56, 214, 255], "fade": 0.6}, "cy_px": 960, "drift": 0.0,
  "headline": "How?", "headline_at": {"word": "How"}, "headline_until": {"word": "Every"},
  "fly": [{"place": "London", "zoom": 14.0}, {"place": "London", "zoom": 1.4, "at": 0.05, "fly": 2.0},
          {"lat": 40, "lon": -60, "zoom": 1.15, "at": {"word": "Every"}, "fly": 1.4},
          {"lat": 38.9, "lon": -77.4, "zoom": 2.0, "at": {"word": "Virginia"}, "fly": 1.0}],
  "cities": [{"place": "London", "at": 0.0, "until": {"word": "Every"}},
             dict(VA, kind="focus", label="Origin server", code="us-east-1 · N. Virginia", at={"word": "origin"}, side="right")],
  "cues": pulse("How", "copy", "origin", "Virginia"),
  "objective": "Pull out to the night Earth; fly to the origin in N. Virginia", "tier": "hypothesis", "recipes": [],
  "reason": "Continues from the clip's last frame; the origin is labelled and glows as it is named."},

 {"id": "s3", "title": "One distant place", "treatment": "motion", "effect": "globe", "transition": "crossfade", "labels": "compact",
  "drift": 0.0, "fly": [{"lat": 45, "lon": -38, "zoom": 1.15}, {"lat": 50, "lon": 40, "zoom": 1.0, "at": 2.4, "fly": 1.4},
                        {"lat": 42, "lon": -40, "zoom": 1.05, "at": {"word": "millions"}, "fly": 1.0}],
  "cities": [dict(VA, kind="region", label="Origin", code="us-east-1", at=0.0, side="left", until={"word": "millions"}),
             {"place": "London", "kind": "focus", "at_frac": 0.08, "side": "right", "until": {"word": "millions"}},
             {"place": "Frankfurt", "kind": "focus", "at_frac": 0.2, "side": "right", "until": {"word": "millions"}},
             {"place": "Seoul", "kind": "focus", "at_frac": 0.33, "side": "right", "until": {"word": "millions"}},
             dict(VA, kind="alert", label="Heavy load", at={"word": "heavy"}, side="right")],
  "arcs": [{"from": "London", "to": VA, "at_frac": 0.08, "tone": "fail", "width": 4},
           {"from": "Frankfurt", "to": VA, "at_frac": 0.2, "tone": "fail", "width": 4},
           {"from": "Seoul", "to": VA, "at_frac": 0.33, "tone": "fail", "width": 4, "dur": 1.4}]
          + [{"from": {"lat": e["lat"], "lon": e["lon"]}, "to": VA, "at": {"word": "millions"}, "tone": "fail", "width": 2.5, "dur": 0.9, "packets": 1, "period": 1.2}
             for e in EDGES if e["name"] in ("Toronto", "Chicago", "Dallas", "Los Angeles", "Miami", "Madrid", "Paris", "Lisbon", "Dublin", "Bogotá", "Lima", "Santiago", "Rio de Janeiro", "Mexico City", "Seattle", "Amsterdam")],
  "cues": pulse("request", "Atlantic", "delay", "millions", "heavy"),
  "objective": "Arcs to London, Frankfurt and Seoul one by one; then many requests converge and the origin pulses red",
  "tier": "hypothesis", "recipes": [], "reason": "The distance and the load on one origin, made visible."},

 {"id": "s4", "title": "Copies near viewers", "treatment": "motion", "effect": "split_compare", "transition": "push",
  "rows": [{"title": "From the factory", "note": "far away", "far": True, "tone": "fail", "via": "truck",
            "from": {"icon": "factory", "label": "Factory"}, "to": {"icon": "house", "label": "You"}, "at": {"word": "factory"}},
           {"title": "From the shop", "note": "down the road", "far": False, "tone": "success", "via": "milk",
            "from": {"icon": "store", "label": "Shop"}, "to": {"icon": "house", "label": "You"}, "at": {"word": "shop"}}],
  "cues": pulse("copies", "milk", "shop", "factory"),
  "objective": "Factory far away vs shop down the road", "tier": "hypothesis", "recipes": [],
  "reason": "The analogy as a clean split card: the travel arrow's length shows the distance."},

 {"id": "s5", "title": "The world tour", "treatment": "motion", "effect": "globe", "transition": "crossfade", "labels": "compact",
  "drift": 0.0, **layers, "edges_from": 0.1,
  "tags": [{"text": "Edge servers", "at": {"word": "edge"}}, {"text": "CDN · content delivery network", "at": {"word": "CDN"}}],
  "counter": {"value": 750, "suffix": "+", "label": "CloudFront locations", "source": "aws.amazon.com/cloudfront/features", "at": {"word": "750"}},
  "fly": fly_tour,
  "cities": [{"place": c, "kind": "focus", "label": c.replace("Sao Paulo", "São Paulo"), "at": {"word": WORD.get(c, c)}, "side": "right",
              "until": {"word": WORD.get(TOUR[i + 1], TOUR[i + 1])} if i + 1 < len(TOUR) else None} for i, c in enumerate(TOUR)],
  "cues": pulse("edge", "CDN", "750", "London", "Mumbai", "Tokyo", "Sao", "York"),
  "objective": "Edge points light up worldwide; the camera visits each named city", "tier": "hypothesis", "recipes": [],
  "reason": "Every AWS Region (small ring) and CloudFront edge location (small point) from the official pages; each named city pulses and is labelled as it is spoken."},

 {"id": "s6", "title": "Open Connect", "treatment": "motion", "effect": "model_3d", "model": "datacenter", "transition": "crossfade",
  "headline": "Netflix Open Connect", "label": "Your internet provider's data centre", "start": 0.45, "scale": 1.2,
  "zoom_in": {"from": 0.5, "dur": 1.0},
  "then": {"model": "server_rack", "at": {"word": "servers"}, "headline": "Open Connect", "label": "Open Connect Appliance",
           "sub": "inside your internet provider", "zoom_in": {"from": 0.5, "dur": 0.9}},
  "cues": pulse("Netflix", "Connect", "servers", "preloaded"),
  "objective": "ISP building, then the Open Connect rack inside it", "tier": "hypothesis", "recipes": [],
  "reason": "The camera goes into the building to the rack."},

 {"id": "s7", "title": "Hit or miss", "treatment": "motion", "effect": "cache_split", "transition": "push",
  "hit_at": {"word": "hit"}, "miss_at": {"word": "miss"}, "fetch_at": {"word": "fetches"}, "keep_at": {"word": "keeps"},
  "proof_title": "real response · 2026-11-23 21:12 UTC · curl -I",
  "proof": [{"text": "X-Cache: Miss from cloudfront", "tone": "err", "at": {"word": "Missing"}},
            {"text": "X-Cache: Hit from cloudfront  Age: 6", "tone": "ok", "at": {"word": "next"}}],
  "cues": pulse("checks", "hit", "Missing", "fetches", "keeps"),
  "objective": "Split screen: hit and miss, with real headers", "tier": "hypothesis", "recipes": [],
  "reason": "Both paths side by side; the real response proves it."},

 {"id": "s8", "title": "Down the road", "treatment": "motion", "effect": "globe", "transition": "crossfade", "labels": "compact",
  "drift": 0.0, "headline": "The show was already down the road.", "headline_at": {"word": "show"},
  "fly": [{"lat": 45, "lon": -20, "zoom": 1.1}, {"place": "London", "zoom": 2.0, "at": 0.3, "fly": 2.2}],
  "cities": [{"place": "London", "kind": "focus", "label": "London", "at": 1.6, "side": "right"}],
  "cues": pulse("instantly", "ocean", "show"),
  "objective": "Back to London at night; the payoff line", "tier": "hypothesis", "recipes": [],
  "reason": "Ends where it began, answering the hook."},
]
for s in scenes:
    if s["treatment"] != "footage":
        s.setdefault("pad_start", 0.25)
        s.setdefault("pad_end", 0.15)
    for ct in s.get("cities", []):
        if ct.get("until") is None:
            ct.pop("until", None)

old = json.loads((H / "research_v3.json").read_text(encoding="utf-8"))
claims = [c for c in old["claims"] if c["id"] not in ("c8", "c13", "c14", "c15")]
claims += [
 {"id": "c8", "text": "Netflix pre-fills embedded Open Connect Appliances with the appropriate content for their geographical location, with nightly content fills and updates.",
  "sources": [{"title": "Netflix Open Connect (read 2026-11-24)", "url": "https://openconnect.netflix.com/en/", "kind": "primary"}], "confidence": "high"},
 {"id": "c13", "text": "CloudFront lists Points of Presence in London, Frankfurt, Mumbai, Singapore, Tokyo, Sydney, São Paulo and New York (among 100+ cities).",
  "sources": [{"title": "Amazon CloudFront features (read 2026-11-24)", "url": "https://aws.amazon.com/cloudfront/features/", "kind": "primary"}], "confidence": "high"},
 {"id": "c14", "text": "An origin server stores the original, definitive version of your objects.",
  "sources": [{"title": "What is Amazon CloudFront? (read 2026-11-24)", "url": "https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Introduction.html", "kind": "primary"}], "confidence": "high"},
 {"id": "c15", "text": "With CloudFront you get a reduced load on your origin because requests that CloudFront can serve from the cache don't go to your origin.",
  "sources": [{"title": "Using Amazon CloudFront Origin Shield (read 2026-11-24)", "url": "https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/origin-shield.html", "kind": "primary"}], "confidence": "high"}]
research = dict(old, claims=claims, arrangement="A Netflix-style video with its origin in AWS us-east-1 (N. Virginia), viewers in London and worldwide; CloudFront edge locations and Netflix Open Connect appliances inside ISP networks serve nearby copies.")
(H / "research_v4.json").write_text(json.dumps(research, ensure_ascii=False, indent=1), encoding="utf-8")
(H / "script_v4.json").write_text(json.dumps(script, ensure_ascii=False, indent=1), encoding="utf-8")
(H / "board_v4.json").write_text(json.dumps({"scenes": scenes}, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(scenes), "scenes;", sum(len(x["text"].split()) for sc in script["scenes"] for x in sc["sentences"]), "words")
