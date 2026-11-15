"""WorkoutPlan -> intervals.icu workout in its native text format.

intervals.icu parses a workout's ``description`` as Markdown: a step is a list
item such as ``- Easy Spin<!> 10m 130-170w intensity=warmup``, and a repeat is
a ``3x`` line sitting directly on top of its step list.
"""

from __future__ import annotations

import re

from app.adapters.base import AdapterResult, PayloadAdapter
from app.models.workout import RepeatStep, WorkoutPlan, WorkoutStep

_SPORT_TYPE: dict[str, str] = {"cycling": "Ride", "running": "Run", "swimming": "Swim"}

# Target types the workout text takes as absolute values. Heart rate is only
# accepted as % of max/threshold HR or as a zone, never in bpm.
_UNITS: dict[str, str] = {"power": "w", "cadence": "rpm"}

# intervals.icu drops a step that has no duration, so an open step gets this
# nominal one plus "press lap", which makes the device wait for the lap button.
_OPEN_STEP_SECONDS = 300

# Text before this marker is the step's cue and is never parsed for durations
# or targets, so a name like "1km Build" cannot override the step's distance.
_CUE_END = "<!>"


def _duration(seconds: int) -> str:
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    parts = ((hours, "h"), (minutes, "m"), (secs, "s"))
    return "".join(f"{value}{unit}" for value, unit in parts if value)


def _range(low: float, high: float) -> str:
    return f"{int(low)}" if low == high else f"{int(low)}-{int(high)}"


def _step_line(step: WorkoutStep, warnings: list[str]) -> str:
    # A name that starts like a list item ("1. Warm-up") would nest a list in
    # the step, which intervals.icu then drops. Without the space after the
    # marker it stays text; a backslash escape would split the step text instead.
    name = re.sub(r"^([-+*]|\d{1,9}[.)]) ", r"\1", " ".join(step.name.split()))
    cue = [name] if name else []
    if step.duration_seconds is None:
        spec = [_duration(_OPEN_STEP_SECONDS), "press", "lap"]
        warnings.append(
            f"Step '{step.type}': intervals.icu needs a duration; open step planned "
            f"as {_duration(_OPEN_STEP_SECONDS)}, ends on lap press"
        )
    elif step.duration_type == "distance":
        spec = [f"{step.duration_seconds}mtr"]
    else:
        spec = [_duration(step.duration_seconds)]

    for target in step.targets:
        value = _range(target.low, target.high)
        unit = _UNITS.get(target.type)
        if unit:
            spec.append(value + unit)
        else:
            cue.append(f"HR {value} bpm")
            warnings.append(
                f"Step '{step.type}': intervals.icu has no absolute heart rate "
                f"targets; {value} bpm kept in the step text"
            )

    spec.append(f"intensity={step.type}")
    text = " ".join(cue)
    return f"- {text}{_CUE_END} {' '.join(spec)}" if text else f"- {' '.join(spec)}"


def _lines(
    steps: tuple[WorkoutStep | RepeatStep, ...], warnings: list[str]
) -> list[str]:
    lines: list[str] = []
    for step in steps:
        if isinstance(step, RepeatStep):
            # intervals.icu has no nested repeats; unrolling keeps the workout.
            lines += _lines(step.steps, warnings) * step.count
        else:
            lines.append(_step_line(step, warnings))
    return lines


def _description(plan: WorkoutPlan, warnings: list[str]) -> str:
    # The plan text goes on one line with any leading list marker escaped, so
    # none of it can parse as a step; blank lines keep each "Nx" header off its
    # neighbours' step lists.
    text = " ".join(plan.description.split())
    text = re.sub(r"^([-+*])", r"\\\1", text)
    # A backslash before a digit is no Markdown escape and would show, so a
    # numbered start is escaped at its dot.
    text = re.sub(r"^(\d{1,9})([.)] )", r"\1\\\2", text)
    # intervals.icu reads a "Power:", "Category:" or "Pool length:" line as a
    # workout option and drops it from the description; an escaped colon stays.
    text = re.sub(r"^((?:power|category|pool length) ?):", r"\1\\:", text, flags=re.I)
    blocks = [text]
    singles: list[str] = []
    for step in plan.steps:
        if isinstance(step, RepeatStep):
            repeat = [f"{step.count}x", *_lines(step.steps, warnings)]
            blocks += ["\n".join(singles), "\n".join(repeat)]
            singles = []
        else:
            singles.append(_step_line(step, warnings))
    blocks.append("\n".join(singles))
    return "\n\n".join(block for block in blocks if block)


class IntervalsWorkoutAdapter(PayloadAdapter):
    @property
    def connector_name(self) -> str:
        return "intervals"

    def to_payload(self, plan: WorkoutPlan) -> AdapterResult:
        warnings: list[str] = []
        payload = {
            "name": plan.name,
            "type": _SPORT_TYPE[plan.sport],
            "description": _description(plan, warnings),
        }
        return AdapterResult(payload=payload, warnings=warnings)
