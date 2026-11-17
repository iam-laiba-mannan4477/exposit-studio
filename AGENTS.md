# Instructions for coding agents working in this repository

Exposit Studio is a local video production studio (Python/FastAPI backend in `exposit/`, React UI in `web/src/`).
This file covers two jobs: **answering role tasks** for a production, and **changing the code**.

## 1. Answering Exposit role tasks (the "agent bridge")

When the studio's AI provider is set to **Agent bridge** (the default, no API cost), each role in a production
(Researcher, Creative Director, Storyteller, Visual Planner, Animation Producer, Quality Reviewer) writes a task file
and waits for an answer.

If the user asks you to "answer the Exposit tasks" (or similar):

1. List the open tasks: `data/bridge/tasks/*.json` (or run `python -m exposit.cli bridge`).
2. For each task file, read it. It contains:
   - `role`: which role you are acting as;
   - `system`: that role's full instructions and the JSON shape it must return;
   - `user`: the input (brief, facts, strategy, ...) as JSON;
   - `result_path`: where your answer goes.
3. Do the work the `system` text describes, for the input in `user`. For the Researcher, verify technical claims
   against official documentation and cite real URLs you have checked; never invent a source.
4. Write **only one JSON object** (no prose, no code fences) to `result_path`, as UTF-8.
   Alternatively: save it to a file and run `python -m exposit.cli bridge answer <task-id> <file.json>`.
5. The studio validates your JSON against the role's schema. If it does not fit, a new task appears for the same role
   with the validation errors appended to `user`; answer that one too.

Rules while answering tasks:
- Do not edit any other file, start or stop the studio, or run anything other than the commands above.
- Do not install anything a task mentions. Tool recommendations are recorded for the user to approve.
- Answer tasks one at a time, in the order they were created; later roles depend on earlier answers.

## 2. Changing the code

- Run the tests before and after a change: `python -m pytest -m "not slow"` (fast), `python -m pytest` (full, ~3 min:
  really narrates and renders at 540p).
- UI: `cd web; npm run dev` serves on http://127.0.0.1:5173 and proxies `/api` to the studio on port 8600.
  Rebuild with `npm run build`; the studio serves `web/dist`.
- Keep the rules in `docs/FEATURE-STATUS.md` true: nothing is shown as working unless it works; planned features are
  labelled "Planned"; no paid service runs without the user's budget; no secret goes into source code.
- Hardware target: 8 GB RAM, integrated graphics, no CUDA. One job at a time (`exposit/app.py` worker).
