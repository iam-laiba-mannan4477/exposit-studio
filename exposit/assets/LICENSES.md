# Third-party assets

Every file under `exposit/assets/` that we did not write ourselves is listed here, with where it came from and the
licence it is used under. All of them allow commercial use. Files are vendored: nothing is fetched at render time.
The full licence texts are in `exposit/assets/licenses/` and next to the fonts. A test checks that every icon file
appears in the lists below.

| Asset | Version | Source | Licence | What we use |
|---|---|---|---|---|
| Lucide icons | 1.77.0 (lucide-static) | https://registry.npmjs.org/lucide-static/-/lucide-static-1.77.0.tgz (https://lucide.dev) | ISC, © 2026 Lucide Icons and Contributors. Icons derived from Feather: MIT, © 2013-present Cole Bemis. Text: `licenses/LICENSE-lucide.txt` | The SVG files in `icons/lucide/`, recoloured at render time |
| Kubernetes icons (unlabeled) | kubernetes/community, master, fetched 2026-11-20 | https://github.com/kubernetes/community/tree/master/icons/svg (resources/unlabeled, infrastructure_components/unlabeled) | CC-BY-4.0 (the set is offered under Apache-2.0 or CC-BY-4.0). Attribution: "Kubernetes icons by the Kubernetes Authors, CC-BY-4.0". The Kubernetes logo is a Linux Foundation trademark and is **not** used | The SVG files in `icons/k8s/`, recoloured at render time; labels are drawn by our renderer |
| World map | world-atlas 2.0.2, land-110m.json | https://unpkg.com/world-atlas@2.0.2/land-110m.json | Packaging ISC, © 2013-2019 Michael Bostock (`licenses/LICENSE-world-atlas.txt`). Data: Natural Earth 1:110m land, public domain ("No permission is needed to use Natural Earth", https://www.naturalearthdata.com/about/terms-of-use/) | `map/land-110m.json`, converted once by `scripts/build_map_asset.py` into land rings and a halftone dot grid |
| Caveat | Variable font, google/fonts main, fetched 2026-11-20 | https://raw.githubusercontent.com/google/fonts/main/ofl/caveat/Caveat%5Bwght%5D.ttf | SIL Open Font License 1.1, © 2014 The Caveat Project Authors (`fonts/OFL-Caveat.txt`) | `fonts/Caveat-Variable.ttf`, labels in the "sketch" template |
| IM FELL English | google/fonts main, fetched 2026-11-22 | https://github.com/google/fonts/tree/main/ofl/imfellenglish | SIL Open Font License 1.1, © 2010 Igino Marini (`fonts/OFL-IMFellEnglish.txt`) | `fonts/IMFellEnglish-Regular.ttf`, titles in the engraving-print and silent-film styles |
| Press Start 2P | google/fonts main, fetched 2026-11-22 | https://github.com/google/fonts/tree/main/ofl/pressstart2p | SIL Open Font License 1.1, © 2012 The Press Start 2P Project Authors, Reserved Font Name "Press Start 2P" (`fonts/OFL-PressStart2P.txt`) | `fonts/PressStart2P-Regular.ttf`, headings in the pixel-art styles |
| Inter | as shipped in 0.1.0 | https://github.com/rsms/inter | SIL Open Font License 1.1 (`fonts/OFL-Inter.txt`) | `fonts/Inter-*.otf`, all interface text |
| Archivo Black | google/fonts main, fetched 2026-11-25 | https://github.com/google/fonts/tree/main/ofl/archivoblack | SIL Open Font License 1.1, © 2017 The Archivo Black Project Authors (`fonts/OFL-ArchivoBlack.txt`) | `fonts/ArchivoBlack-Regular.ttf`, the heavy title face in the claude-warm-dark style |
| JetBrains Mono | as shipped in 0.1.0 | https://github.com/JetBrains/JetBrainsMono | SIL Open Font License 1.1 (`fonts/OFL-JetBrainsMono.txt`) | `fonts/JetBrainsMono-Regular.ttf`, code and blueprint labels |

| NASA Blue Marble: Next Generation (day), December 2004, topography and bathymetry | world.topo.bathy.200412.3x5400x2700.jpg, fetched 2026-11-24 | https://science.nasa.gov/earth/earth-observatory/blue-marble-next-generation/ | NASA imagery is generally not subject to copyright in the United States (https://www.nasa.gov/nasa-brand-center/images-and-media/, read 2026-11-24). Credit "NASA Earth Observatory" as the BMNG page asks. No NASA insignia or logos are used, and nothing implies NASA endorsement | `earth/day-4096.jpg`, resized to 4096x2048 by `scripts/build_earth_assets.py`; the day side of the globe and flat maps |
| NASA Black Marble 2016 (Earth at Night), colour, 0.1 degree | BlackMarble_2016_01deg.jpg (3600x1800), fetched 2026-11-24 | https://science.nasa.gov/earth/earth-observatory/earth-at-night/maps | As above (NASA image use policy); credit "NASA Earth Observatory" | `earth/night-4096.jpg`, resized to 4096x2048; the night side and city lights |
| Natural Earth 1:50m: admin 0 boundary lines (land) 5.1.0, coastline 4.0.0, populated places 5.1.2 | ne_50m_*.zip, fetched 2026-11-24 from naciscdn.org | https://www.naturalearthdata.com/downloads/50m-cultural-vectors/, /50m-physical-vectors/ | Public domain: "All versions of Natural Earth raster + vector map data found on this website are in the public domain" (https://www.naturalearthdata.com/about/terms-of-use/, read 2026-11-24). Credit given anyway | `earth/vectors-50m.json` (borders, coastlines, places), converted by `scripts/build_earth_assets.py` (needs pyshp, a dev requirement only) |

Credit "Imagery: NASA Earth Observatory. Map data: Natural Earth." is written to sources.md of every video with a globe or flat_map scene (not drawn on screen).

| CDN Reel opening (footage) | cdn-opening-9x16.mp4 (1080x1920, 30 fps, 4.8 s) and cdn-opening-timing.json, added 2026-11-24 | Supplied by the channel owner | Owned by the channel owner (TechHub). Room, sofa, viewer and lighting: AI-generated by the channel owner with ChatGPT. TV screens (splash, home UI, tiles): original TechHub artwork. No Netflix logo, no real shows or people | `footage/`, played as-is by the "footage" scene type with its own sound effects |

| Pixel mascot sprite | assets/brand/clawd-sunglasses.png (48x48), added 2026-11-25 | Supplied by the channel owner | Icons8 (icons8.com); credit "Sprite: Icons8 (icons8.com)" goes in the post caption. Not affiliated with Anthropic | Drawn by `render/mascot.py` at integer scale with nearest-neighbour sampling, split into body and glasses layers from its own pixels; never redrawn |

Not used, and why: AWS Architecture Icons (AWS permits them in diagrams, presentations and documents but its page
does not mention video, so their use here is unclear); Tabler and Phosphor (not needed; one icon family keeps one style).

## Icon files

lucide: activity arrow-down arrow-left arrow-right arrow-right-left arrow-up ban bell blocks book-open box braces building-2 check chevron-down chevron-right circle-check circle-x clock cloud cloud-download cloud-upload code container cpu database database-zap earth ellipsis eye factory file file-code file-cog file-json file-terminal file-text files filter fingerprint flask-conical folder folder-open gauge git-branch git-merge globe hard-drive house inbox info key laptop layers link list list-ordered lock mail map-pin memory-stick merge message-square milk minus monitor network package play plug plus-circle radio-tower refresh-cw repeat rocket rotate-ccw route router scale search send server server-cog settings shield shield-check smartphone split square square-terminal store terminal timer triangle-alert truck user users waypoints wifi workflow x zap

k8s: cm control-plane deploy ds hpa ing job node ns pod pvc rs secret sts svc

## Optional external tool: Blender
Blender (https://www.blender.org) is GPL-licensed. It is not bundled, downloaded or installed by the studio; the user
installs it. The studio runs it headless with `--factory-startup` (no add-ons) on scripts the studio generates; the
scripts and the rendered frames are our own output. 3D scenes use primitives and procedural materials only; the
optional globe uses the NASA image already listed above.
