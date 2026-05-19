from __future__ import annotations

import math

from app.models.workout import (
    SUPPORTED_SPORTS,
    SUPPORTED_STEP_TYPES,
    SUPPORTED_TARGET_TYPES,
    RepeatStep,
    Target,
    WorkoutPlan,
    WorkoutStep,
)


def _require_positive_int(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"'{field}' must be a positive integer, got bool")
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"'{field}' must be a positive integer, got {value!r}")
    if not isinstance(value, (int, float)):
        raise ValueError(f"'{field}' must be a positive integer")
    result = int(value)
    if result <= 0:
        raise ValueError(f"'{field}' must be positive, got {result}")
    return result


def _parse_target(data: dict) -> Target:
    if not isinstance(data, dict):
        raise ValueError(f"Each target must be an object, got {type(data).__name__!r}")
    target_type = data.get("type")
    if target_type not in SUPPORTED_TARGET_TYPES:
        supported = sorted(SUPPORTED_TARGET_TYPES)
        raise ValueError(
            f"Unknown target type: {target_type!r}. Supported: {supported}"
        )
    low = data.get("low")
    high = data.get("high")
    if low is None:
        raise ValueError(f"Target {target_type!r} missing 'low'")
    if high is None:
        raise ValueError(f"Target {target_type!r} missing 'high'")
    if isinstance(low, bool) or isinstance(high, bool):
        raise ValueError(
            f"Target {target_type!r} 'low' and 'high' must be numeric, got bool"
        )
    try:
        low_f, high_f = float(low), float(high)
    except (TypeError, ValueError) as err:
        raise ValueError(
            f"Target {target_type!r} 'low' and 'high' must be numeric"
        ) from err
    if not math.isfinite(low_f) or not math.isfinite(high_f):
        raise ValueError(
            f"Target {target_type!r} 'low' and 'high' must be finite numbers"
        )
    if not low_f.is_integer() or not high_f.is_integer():
        raise ValueError(
            f"Target {target_type!r} 'low' and 'high' must be whole numbers"
        )
    if low_f > high_f:
        raise ValueError(f"Target {target_type!r} has low={low_f} > high={high_f}")
    return Target(type=target_type, low=low_f, high=high_f)


def _parse_repeat_step(data: dict, depth: int = 0) -> RepeatStep:
    if depth >= 1:
        raise ValueError(
            "Nested repeat steps are not supported (max nesting depth is 1)"
        )
    count = data.get("count")
    if count is None:
        raise ValueError("Repeat step missing 'count'")
    count_i = _require_positive_int(count, "count")
    nested = data.get("steps")
    if not nested:
        raise ValueError("Repeat step missing 'steps'")
    if not isinstance(nested, list):
        raise ValueError("Repeat step 'steps' must be a list")
    return RepeatStep(
        count=count_i,
        steps=tuple(_parse_step(s, depth=depth + 1) for s in nested),
    )


def _parse_step(data: dict, depth: int = 0) -> WorkoutStep | RepeatStep:
    if not isinstance(data, dict):
        raise ValueError(f"Each step must be an object, got {type(data).__name__!r}")
    step_type = data.get("type")
    if step_type == "repeat":
        return _parse_repeat_step(data, depth=depth)
    if step_type not in SUPPORTED_STEP_TYPES:
        supported = sorted(SUPPORTED_STEP_TYPES)
        raise ValueError(f"Unknown step type: {step_type!r}. Supported: {supported}")
    raw_name = data.get("name", "")
    if not isinstance(raw_name, str):
        raise ValueError(f"Step {step_type!r} 'name' must be a string")
    name = raw_name.strip()
    duration = data.get("duration_seconds")
    if duration is None:
        raise ValueError(f"Step {step_type!r} missing 'duration_seconds'")
    duration_i = _require_positive_int(duration, "duration_seconds")
    raw_targets = data.get("targets", [])
    if not isinstance(raw_targets, list):
        raise ValueError(f"Step {step_type!r} 'targets' must be a list")
    targets = tuple(_parse_target(t) for t in raw_targets)
    seen: set[str] = set()
    for t in targets:
        if t.type in seen:
            raise ValueError(f"Step {step_type!r}: duplicate target type {t.type!r}")
        seen.add(t.type)
    return WorkoutStep(
        type=step_type,
        duration_seconds=duration_i,
        targets=targets,
        name=name,
    )


def parse_workout(data: dict) -> WorkoutPlan:
    if not isinstance(data, dict):
        raise ValueError(f"Plan must be a JSON object, got {type(data).__name__!r}")
    name = data.get("name")
    if not isinstance(name, str):
        raise ValueError(f"Plan 'name' must be a string, got {type(name).__name__!r}")
    if not name.strip():
        raise ValueError("Plan 'name' must not be empty or whitespace-only")
    sport = data.get("sport")
    if sport not in SUPPORTED_SPORTS:
        raise ValueError(
            f"Unknown sport: {sport!r}. Supported: {sorted(SUPPORTED_SPORTS)}"
        )
    steps = data.get("steps")
    if not steps:
        raise ValueError("Plan missing 'steps'")
    if not isinstance(steps, list):
        raise ValueError("Plan 'steps' must be a list")
    return WorkoutPlan(
        name=name,
        sport=sport,
        steps=tuple(_parse_step(s) for s in steps),
    )
