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
| JetBrains Mono | as shipped in 0.1.0 | https://github.com/JetBrains/JetBrainsMono | SIL Open Font License 1.1 (`fonts/OFL-JetBrainsMono.txt`) | `fonts/JetBrainsMono-Regular.ttf`, code and blueprint labels |

Not used, and why: AWS Architecture Icons (AWS permits them in diagrams, presentations and documents but its page
does not mention video, so their use here is unclear); Tabler and Phosphor (not needed; one icon family keeps one style).

## Icon files

lucide: activity arrow-down arrow-left arrow-right-left arrow-right arrow-up ban bell box braces building-2 check circle-check circle-x clock cloud-download cloud-upload cloud code container cpu database-zap database earth eye file-code file-text file filter fingerprint folder gauge git-branch git-merge globe hard-drive inbox info key laptop layers link list-ordered list lock mail map-pin memory-stick merge message-square monitor network package plug radio-tower refresh-cw repeat rocket rotate-ccw route router scale search send server-cog server settings shield-check shield smartphone split terminal timer triangle-alert user users waypoints wifi workflow x zap

k8s: cm control-plane deploy ds hpa ing job node ns pod pvc rs secret sts svc
