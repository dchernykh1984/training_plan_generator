---
name: plan-upload
description: How training_plan_generator turns a plan definition into structured workouts and uploads them to a training service. Use when working on plan parsing, workout building, or the upload path. Contains no secrets.
---

# Plans, templates, and uploads

- The tool reads a plan definition and produces structured workouts to upload to a
  training service. Plan shapes live in `templates/`; `examples/` has runnable samples,
  which are the best fixtures for tests.
- Keep plan parsing/validation and workout building as pure functions, out of the CLI
  (`app/cli.py`) and GUI (`app/gui/app.py`) shells, so they stay unit-testable. Cover them
  with the example inputs plus malformed variants.
- Any service credential or token is provided at runtime and is a SECRET: never hardcode,
  log, or commit it. In tests never call the real service - patch the client and assert on
  the structured-workout request it would send.
