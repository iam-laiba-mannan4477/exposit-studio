# Creative strategy: How an HTTP request reaches a Kubernetes app

**Audience.** Developers who deploy to Kubernetes but have not traced a request end to end. They know HTTP, IP addresses and containers; those are not explained.

**Learning objective.** After watching, the viewer can name the four decisions that route a request from the browser to a pod, in order, and knows that a Service is a name and not a running program.

**Concept.** One request is the protagonist. A single map is revealed left to right; the camera enters the AWS box as an isometric scene and the cluster as a cutaway, then pulls back to the whole map.

**Hook.** You press Enter. Before the page appears, four decisions are made about where your request goes.

**Narrative structure.** Follow the request: hook with a count, then one scene per decision (address, node, Service, pod), a misconception beat at the Service, and a recap that returns to the opening line.

**Visual direction.** Three treatments, each where its form carries meaning: a 2D network-flow map as the spine; an isometric scene for the load balancer, because zones and health are spatial; a cutaway for the cluster, because it has an inside. Dark premium-technical theme, one accent colour, the request as a glowing token.

**Narration.** Calm, present tense, second person. About 150 words. One idea per sentence. Kokoro voice am_michael on the local machine.

## Treatments compared

### A. Follow the request (chosen)
One request travels through four decisions, left to right, with one misconception beat at the Service.

- Engagement: strong
- Teaching fit: strong
- Accuracy risk: low
- Feasibility: Fits: CPU rendering, no paid service

Chosen. The subject is a path, so the path is the story.

### B. Misconception throughout
Open with 'the load balancer has no idea your app exists' and rebuild the true picture.

- Engagement: strong
- Teaching fit: medium
- Accuracy risk: medium
- Feasibility: Fits

Not chosen: needs more than 60 seconds to rebuild the picture honestly. Its best beat is borrowed for the Service scene.

### C. Failure story
Trace a 502 error backwards to its cause.

- Engagement: strong
- Teaching fit: weak
- Accuracy risk: medium
- Feasibility: Fits

Not chosen: teaches the broken path before the working one. A good sequel.

## Decisions and reasons

| Decision | Choice | Reason | Evidence |
| --- | --- | --- | --- |
| Audience | Intermediate developers who deploy to Kubernetes | From the brief. Basics such as what an IP address is are skipped. | preference |
| Hook | A concrete action plus a count: four decisions before the page appears | A count gives the viewer a structure to track, and the video keeps the promise. | hypothesis |
| Structure | Follow the request, with one misconception beat | The path supplies the order; the misconception supplies the one surprise. | observation |
| Visual treatments | 2D flow map, isometric AWS scene, Kubernetes cutaway | You asked for three treatments. Each sits where its form teaches: a path as a line, zones as plates, a cluster as an opened box. | preference |
| Use of 3D | Isometric projection drawn in 2D; no 3D engine | Depth is only needed to show zones side by side. A flat projection renders as fast as any 2D scene on this laptop. | hypothesis |
| Pacing | A visual change every 2 to 4 seconds; about 150 words | Dense enough for this audience, with room for the surprise to land. | observation |
| Where the surprise goes | At the Service, two thirds through | That is where attention is most likely to sag, and it is the idea most viewers hold wrongly. | hypothesis |
| Ending | Return trip, then echo the opening line over the whole map | Answers the opening question and leaves a frame worth pausing on. | hypothesis |
| Narration | Second person, present tense, local Kokoro voice | Explains as to a capable colleague; costs nothing. | preference |
| Tools | Local renderer, Kokoro, FFmpeg; no paid service | The budget for paid services is zero and nothing here needs a GPU. | preference |

## Scene breakdown

| Scene | Treatment | Seconds | Purpose |
| --- | --- | --- | --- |
| Hook | kinetic | 7.0 | State the question and the count of four |
| DNS | flow2d | 9.0 | Decision one: which address |
| AWS load balancer | isometric | 11.0 | Decision two: which healthy node |
| NGINX ingress | cutaway | 11.0 | Decision three: which Service |
| Service to pod | cutaway | 12.0 | The surprise: a Service is not a program. Decision four: which pod |
| Response and recap | flow2d | 10.0 | Return trip and the whole route in one frame |

## Likely drop-off points (hypotheses)

- **DNS, around 8 seconds**: Viewers who know DNS may leave. Countermeasure: The step marker shows this is one of four.
- **NGINX, around 30 seconds**: Risk of a text-heavy stretch. Countermeasure: Three short lines of rule, highlighted as they are spoken.
- **Before the Service scene**: Mid-video sag. Countermeasure: The scene opens on the word 'But' and a struck-through assumption.

**Experiment in this video.** The count from the hook stays on screen as a step marker (1 of 4 to 4 of 4).

**Tools.** Skia scene renderer (local), Kokoro (local), FFmpeg (local)
