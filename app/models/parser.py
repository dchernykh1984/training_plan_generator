from __future__ import annotations

import math

from app.models.workout import (
    SUPPORTED_DURATION_TYPES,
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


_TARGET_RANGES: dict[str, tuple[float, float]] = {
    "power": (0, 2500),
    "cadence": (0, 220),
    "heart_rate": (20, 250),
}


def _parse_target_value(
    target_type: str, field: str, raw: int | float | str | None
) -> float:
    if raw is None:
        raise ValueError(f"Target {target_type!r} missing {field!r}")
    if isinstance(raw, bool):
        raise ValueError(
            f"Target {target_type!r} 'low' and 'high' must be numeric, got bool"
        )
    try:
        value = float(raw)
    except (TypeError, ValueError) as err:
        raise ValueError(
            f"Target {target_type!r} 'low' and 'high' must be numeric"
        ) from err
    if not math.isfinite(value):
        raise ValueError(
            f"Target {target_type!r} 'low' and 'high' must be finite numbers"
        )
    if not value.is_integer():
        # If float targets are needed for future adapters, relax this check
        # and push int-casting to the adapter (e.g. GarminWorkoutAdapter).
        raise ValueError(
            f"Target {target_type!r} 'low' and 'high' must be whole numbers"
        )
    range_min, range_max = _TARGET_RANGES[target_type]
    if value < range_min or value > range_max:
        raise ValueError(
            f"Target {target_type!r} {field!r} value {value} out of range "
            f"[{range_min}, {range_max}]"
        )
    return value


def _parse_target(data: dict) -> Target:
    if not isinstance(data, dict):
        raise ValueError(f"Each target must be an object, got {type(data).__name__!r}")
    target_type = data.get("type")
    if not isinstance(target_type, str):
        raise ValueError(
            f"target type must be a string, got {type(target_type).__name__!r}"
        )
    if target_type not in SUPPORTED_TARGET_TYPES:
        supported = sorted(SUPPORTED_TARGET_TYPES)
        raise ValueError(
            f"Unknown target type: {target_type!r}. Supported: {supported}"
        )
    low_f = _parse_target_value(target_type, "low", data.get("low"))
    high_f = _parse_target_value(target_type, "high", data.get("high"))
    if low_f > high_f:
        raise ValueError(f"Target {target_type!r} has low={low_f} > high={high_f}")
    return Target(type=target_type, low=low_f, high=high_f)


def _parse_duration(
    step_type: str, duration_type: str, raw_duration: object
) -> int | None:
    if duration_type not in SUPPORTED_DURATION_TYPES:
        raise ValueError(
            f"Step {step_type!r} unknown duration_type: {duration_type!r}. "
            f"Supported: {sorted(SUPPORTED_DURATION_TYPES)}"
        )
    if duration_type == "open":
        if isinstance(raw_duration, bool):
            raise ValueError(
                f"Step {step_type!r} 'duration_seconds' must be absent or null "
                f"for duration_type='open', got bool"
            )
        if raw_duration is not None and raw_duration != 0:
            raise ValueError(
                f"Step {step_type!r} 'duration_seconds' must be absent or null "
                f"for duration_type='open'"
            )
        # 0 is treated the same as absent/null for "open" steps
        return None
    if raw_duration is None:
        raise ValueError(f"Step {step_type!r} missing 'duration_seconds'")
    return _require_positive_int(raw_duration, "duration_seconds")


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
    if not isinstance(step_type, str):
        raise ValueError(
            f"step type must be a string, got {type(step_type).__name__!r}"
        )
    if step_type not in SUPPORTED_STEP_TYPES:
        supported = sorted(SUPPORTED_STEP_TYPES)
        raise ValueError(f"Unknown step type: {step_type!r}. Supported: {supported}")
    raw_name = data.get("name", "")
    if not isinstance(raw_name, str):
        raise ValueError(f"Step {step_type!r} 'name' must be a string")
    name = raw_name.strip()
    duration_type = data.get("duration_type", "time")
    if not isinstance(duration_type, str):
        raise ValueError(f"Step {step_type!r} 'duration_type' must be a string")
    duration_i = _parse_duration(step_type, duration_type, data.get("duration_seconds"))
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
        duration_type=duration_type,
    )


def _parse_estimated_tss(raw: object) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        raise ValueError("Plan 'estimated_tss' must be a non-negative number, got bool")
    if not isinstance(raw, (int, float)):
        raise ValueError("Plan 'estimated_tss' must be a non-negative number")
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError("Plan 'estimated_tss' must be a finite number")
    if value < 0:
        raise ValueError("Plan 'estimated_tss' must be non-negative")
    return value


def _parse_ftp_watts(raw: object) -> int | None:
    if raw is None:
        return None
    return _require_positive_int(raw, "ftp_watts")


def parse_workout_file(data: object) -> dict[str, WorkoutPlan]:
    """Parse a plan file containing one workout or a named dict of workouts.

    Single-workout format (top-level dict has both ``"name"`` and ``"steps"``):
        ``{"name": "...", "sport": "cycling", "steps": [...]}``
    Dict-of-workouts format (top-level keys are arbitrary workout identifiers):
        ``{"key_a": {"name": "...", ...}, "key_b": {"name": "...", ...}}``
    """
    if not isinstance(data, dict):
        raise ValueError(
            f"Plan file must be a JSON object, got {type(data).__name__!r}"
        )
    if "name" in data and "steps" in data:
        plan = parse_workout(data)
        return {plan.name: plan}
    if not data:
        raise ValueError("Plan file must not be empty")
    return {key: parse_workout(val) for key, val in data.items()}


def parse_workout(data: dict) -> WorkoutPlan:
    if not isinstance(data, dict):
        raise ValueError(f"Plan must be a JSON object, got {type(data).__name__!r}")
    name = data.get("name")
    if not isinstance(name, str):
        raise ValueError(f"Plan 'name' must be a string, got {type(name).__name__!r}")
    if not name.strip():
        raise ValueError("Plan 'name' must not be empty or whitespace-only")
    sport = data.get("sport")
    if not isinstance(sport, str):
        raise ValueError(f"Plan 'sport' must be a string, got {type(sport).__name__!r}")
    if sport not in SUPPORTED_SPORTS:
        raise ValueError(
            f"Unknown sport: {sport!r}. Supported: {sorted(SUPPORTED_SPORTS)}"
        )
    steps = data.get("steps")
    if not steps:
        raise ValueError("Plan missing 'steps'")
    if not isinstance(steps, list):
        raise ValueError("Plan 'steps' must be a list")
    raw_desc = data.get("description", "")
    if not isinstance(raw_desc, str):
        raise ValueError("Plan 'description' must be a string")
    description = raw_desc.strip()
    estimated_tss = _parse_estimated_tss(data.get("estimated_tss"))
    ftp_watts = _parse_ftp_watts(data.get("ftp_watts"))
    return WorkoutPlan(
        name=name,
        sport=sport,
        steps=tuple(_parse_step(s) for s in steps),
        description=description,
        estimated_tss=estimated_tss,
        ftp_watts=ftp_watts,
    )
