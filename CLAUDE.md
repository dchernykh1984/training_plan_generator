# Working in training_plan_generator

A Python 3.14 tool that builds structured workout plans and uploads them to a training
service. It ships a CLI (`app/cli.py`, entry point `training-plan-generator`) and a
PySide6 GUI (`app/gui/app.py`, `training-plan-generator-gui`). Plan shapes live in
`templates/`; `examples/` holds runnable sample inputs.

## Conventions

- Python 3.14, everything through uv: `uv run pytest`, `uv run ruff check .`,
  `uv run mypy app tests`.
- Never commit to `main`. Branch off `origin/main`, one logical change per commit.
- Commit messages: one-line Conventional Commits, no body, no `Co-Authored-By` trailer
  and no co-author line. `cz check --rev-range origin/main..HEAD` runs on every PR, and
  release-please builds `CHANGELOG.md` from these subjects, so the type matters (`fix`
  and `feat` are released; `chore`/`docs`/`test`/`style`/`refactor` are not).
- ASCII only in tracked files (`uv.lock` and `CHANGELOG.md` are exempt). A pre-commit
  hook and the `.claude` PostToolUse guard both enforce it. Chat in any language; files
  stay ASCII.
- Before committing run the full gate: `uv run pytest` (coverage gate 90%),
  `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy app tests`.
  `uv run` may rewrite `uv.lock`; keep it out of feature commits with
  `git checkout uv.lock` unless the lock itself is the change.

## Skills

- `shipping-a-change` - branch, commit, open the PR, watch CI to green.
- `review-cycle` - review a branch or PR and land the fixes.
- `plan-upload` - plans, templates, and the upload path.
