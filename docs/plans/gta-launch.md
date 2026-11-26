# "How do you ship a 212 GB game to millions at midnight?" (2026-11-27)

Produced as **pbefe34368b** (midnight-launch, 9:16, 1080p, am_michael 1.1, captions off, music off, narrated end slide).
Plan and files: `gta-launch/`. Public facts only; techniques framed as how a launch like this works; no game art or logos.

- Facts checked 2026-11-27 (sources.md): up to 212 GB (Rockstar); preloads from 10 Nov (Rockstar Newswire); rolling
  midnight unlock from New Zealand (Rockstar Support); 32.5 M pre-release units (Take-Two 8-K); Comcast's 48-hour record
  (Newsweek quoting Comcast); patch ~1.07 GB on PS5; PSN status-page outages on 18 Nov (no cause given); PS5 licence
  and offline play (PlayStation Support). "About 15 waves" and the Xbox patch size could not be verified and were dropped.
- 65.7 s + 8.2 s narrated end slide; target 66 s. All 11 final checks pass.
- Blender shots rendered by the studio at 720x1280: S3 network3d 67 s / 1.9 GB, S5 globe3d 133 s / 2.3 GB.
- Known: the S5 midnight band renders as solid orange (emission ignores the band's transparency), hiding the land under it.
- The strategy gate holds on "two to six motion effects": this video uses one (dev_scene) plus two blender3d shots.
- S4 was re-rendered in a one-off process (the studio had the old scene code loaded) to fix near-empty frames.
