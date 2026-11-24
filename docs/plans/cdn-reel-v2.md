# CDN Reel v2: plan and state (paused 2026-11-24)

A new production from scratch. The previous production, `p52ef24a058`, is not good enough. Prepared files are in
`docs/plans/cdn-reel-v2/`.

## Brief (to create with POST /api/productions)
- Title: "How a CDN serves your request from the edge". Topic: CDNs explained, with Amazon CloudFront and Netflix
  Open Connect as the real examples.
- Format: 60 s, 9:16, 1080p, captions off, voice am_michael, **voice speed 1.1**.
- Audience: senior engineers. Precise, no hype, no emojis.
- Template: noir-network, the user's explicit override of the variety rule. Record it through the studio's override
  mechanism after the strategy exists: `POST /api/productions/{pid}/strategy/override` with
  `{"key": "template", "choice": "noir-network"}`.
- Up to 6 motion effects. The gate now allows 2–6.
- Locations: London, Frankfurt, Seoul, Tokyo, São Paulo, Sydney, New York. No Karachi or Pakistan.

## Hard rules (done in code)
- No floating hexagons or decorative shapes in any template. `parallax` is now faint drifting line grids.
- Pronunciation: `us-east-1` → "U S East 1" (jˈuː ˈɛs ˈiːst wˈʌn); `CDN` → "C D N"; CloudFront reads as
  klˈaʊd fɹˈʌnt. Checked with `kokoro().tokenizer.phonemize` before recording.
- No on-screen imagery credit. `sources.md` gets "Imagery: NASA Earth Observatory. Map data: Natural Earth."
  automatically when a globe or flat_map scene is used. The user puts "Imagery: NASA Earth Observatory" in the
  Instagram caption.
- Every fact and number comes from an official page opened that day.

## Assets (done)
- NASA Blue Marble NG (Dec 2004) day and Black Marble 2016 night textures, 4096x2048, in `exposit/assets/earth/`.
- Natural Earth 50m borders, coastlines and populated places, in `vectors-50m.json`.
- Licences are recorded in `exposit/assets/LICENSES.md`. Built by `scripts/build_earth_assets.py`, which needs pyshp
  (`requirements-dev.txt` only).
- New motion effects:
  - `globe`: textured orthographic sphere, camera `fly` keyframes, `cities`, `arcs` with light-trail packets,
    `headline`, `sun`. 55–80 ms per 1080p frame.
  - `flat_map`: regional map from the same imagery, with borders.

## Research (prepared: `research.json`, sources opened 2026-11-24)
- us-east-1 = US East (N. Virginia): https://docs.aws.amazon.com/global-infrastructure/latest/regions/aws-regions.html
- CloudFront "750+ POPs in 100+ cities across 50+ countries", "15 RECs globally": https://aws.amazon.com/cloudfront/features/
- How CloudFront delivers content (nearest POP, hit, miss): https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/HowCloudFrontWorks.html
- Hit and Miss in logs: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/standard-logs-reference.html
- X-Cache wording (AWS re:Post Knowledge Center): https://repost.aws/knowledge-center/cloudfront-custom-object-caching
- Age header: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Age
- Netflix Open Connect: "Open Connect Appliances can be embedded in your ISP network", interconnection at "public
  Internet Exchange fabrics", "pre-fills them with the appropriate content for your geographical location":
  https://openconnect.netflix.com/en/ and https://openconnect.netflix.com/en/appliances/
- Real response captured with `curl -I` against a d1.awsstatic.com image, 2026-11-23 21:12 UTC: Miss, then 5 s later
  Hit with Age: 6. Full text in `curl-real-response.txt`. Do not show `X-Amz-Cf-Pop`, because it reveals the
  user's nearest location.

## Scout (done 2026-11-24)
Repositories read (not installed): liuantum/cinelume, Remocn/remocn, ZuanCrisp/Motion-Agent-AI-Agents,
necromancer124/clapcode, Makkov-design/framelens.

Techniques adopted:
- camera fly-to between cities (cinelume: "maps that fly to countries")
- light-trail packets
- kinetic number counter with a source line (cinelume `bignumber`)
- split-screen comparison
- staggered build, one focal action per beat (remocn, clapcode)

## Scene plan (prepared: `board.py` → `board.json`, `script.json`; 150 words)
| # | Scene | Treatment / effect | Narration |
|---|---|---|---|
| s1 | Hook | globe, night, fly into London, headline | You press play on Netflix in London. It starts almost instantly. Why? |
| s2 | Without a CDN | globe, arcs from us-east-1 to London, Frankfurt, Seoul | Without a CDN, the video lives on one origin in us-east-1. London, Frankfurt and Seoul all wait on it. |
| s3 | The CDN idea | stat 750+ with source line, parallax grid | A CDN keeps copies of popular content near viewers. CloudFront alone runs more than 750 points of presence. |
| s4 | Across the globe | globe, cities light up as named, fly between them | Over 50 countries: London, Frankfurt, Seoul, Tokyo, Sao Paulo, Sydney. |
| s5 | Netflix Open Connect | model_3d server_rack, headline | Netflix runs its own CDN, called Open Connect. |
| s6 | Inside your ISP | iconflow viewer ← appliance ← IXP, focus_frame | Its servers sit inside internet providers and at exchange points, pre-filled for each region. |
| s7 | Miss vs hit | compare (split screen), Frankfurt | The first viewer in Frankfurt causes a cache miss. The next viewer gets a hit, served from the edge. |
| s8 | On a miss | sequence | On a miss, the edge fetches from the origin, keeps a copy, and responds. |
| s9 | Real proof | scroll_demo, "real response · 2026-11-23 21:12 UTC" | A real CloudFront response: First request: Miss from cloudfront. Five seconds later: Hit, and Age is six. |
| s10 | Why it is fast | stacking_cards (3 benefits + payoff) | Lower latency, less origin load, room for traffic spikes. It starts fast because the video was already near you. |

Effects (6): globe, model_3d, focus_frame, scroll_demo, stacking_cards, parallax.

The strategy answer for the Creative Director must list 3+ treatments and 5+ decisions with reasons. See
`strategy-v1-reference.json` for the shape.

## Previews (2026-11-24, 540x960, real narration at speed 1.1, rendered locally with `preview.py`)
- s1 hook and s5+s6 (Netflix) rendered well. The stills sheet is in `stills-sheet-preview.png`.
- Narration was 58.6 s. With scene pads the content is about 67.5 s, against the 65 s maximum.

## Decisions for tomorrow
1. **Trim 6–8 words** from the narration and **keep voice speed 1.1**. Candidates: s3 "alone", s6 "for each
   region" → "by region", s10 "It starts fast because" → "It starts fast:", s7 "served from the edge" → "from the
   edge".
2. **Fix the s5 rack:** it reads as a flat blue slab. Improve the model: shading, front panel, smaller headline gap.
3. **Fix globe framing:** reduce the empty space under the globe in s1, s2 and s4. Bring the s1 zoom back so the limb
   doesn't cut awkwardly.
4. **London in s2:** keep London visible after the camera turns to Seoul. Either end the fly with London on the
   limb, or zoom out instead of rotating.

## Then
Start the studio (the user restarts it so it loads the new code). Create the production and answer each task with
the prepared files: research, strategy, script, reviewer, storyboard. Record the template override. Render at
1080p, run the final checks (content 60 ± 5 s), regenerate the cover, rebuild the scene sheet beside the
references, report the MP4 and cover paths, then commit, run the fast tests and push.

## Process note
When muxing preview audio, do not use `apad` with `-shortest` and a copied video stream (ffmpeg hangs). Use
`-t <scene duration>` instead, as `preview.py` now does.

## Status 2026-11-24
Produced as p0bac96c577: all final checks pass (63.6 s content + 8.2 s end slide), cover regenerated, credit in sources.md.
