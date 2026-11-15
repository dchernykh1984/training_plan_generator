"""WorkoutPlan -> Zwift workout file (.zwo).

Zwift sets power as a share of FTP and holds one value per step, so power
targets need the plan's ``ftp_watts`` and each range becomes its middle.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from app.adapters.base import AdapterResult, PayloadAdapter
from app.models.workout import RepeatStep, Target, WorkoutPlan, WorkoutStep

# Zwift steps are always timed, so an open or distance step gets this duration.
_FALLBACK_SECONDS = 300

# Zwift labels these blocks; equal low and high power keep them flat.
_RAMP_ELEMENTS = {"warmup": "Warmup", "cooldown": "Cooldown"}


def _middle(target: Target) -> float:
    return (target.low + target.high) / 2


def _flatten(steps: tuple[WorkoutStep | RepeatStep, ...]) -> list[WorkoutStep]:
    flat: list[WorkoutStep] = []
    for step in steps:
        if isinstance(step, RepeatStep):
            # Each step keeps its own name this way, which a Zwift interval
            # block of exactly two steps could not.
            flat += _flatten(step.steps) * step.count
        else:
            flat.append(step)
    return flat


def _element(step: WorkoutStep, ftp: int | None, warnings: list[str]) -> ET.Element:
    seconds = step.duration_seconds
    if step.duration_type != "time" or seconds is None:
        what = "open" if seconds is None else f"{seconds} m"
        warnings.append(
            f"Step '{step.type}': Zwift steps are timed; {what} step planned as "
            f"{_FALLBACK_SECONDS // 60}m"
        )
        seconds = _FALLBACK_SECONDS
    attrs = {"Duration": str(seconds)}
    targets = {t.type: t for t in step.targets}

    tag = "FreeRide"
    power = targets.get("power")
    if power is not None and ftp is None:
        warnings.append(
            "Zwift sets power as a share of FTP; add ftp_watts to the plan to keep "
            "its power targets"
        )
    elif power is not None and ftp is not None:
        share = str(round(_middle(power) / ftp, 3))
        tag = _RAMP_ELEMENTS.get(step.type, "SteadyState")
        if tag == "SteadyState":
            attrs["Power"] = share
        else:
            attrs["PowerLow"] = attrs["PowerHigh"] = share
        if power.low != power.high:
            warnings.append(
                "Zwift holds one power per step; each power range is set to its middle"
            )
    cadence = targets.get("cadence")
    if cadence is not None:
        attrs["Cadence"] = str(round(_middle(cadence)))

    element = ET.Element(tag, attrs)
    cue = [" ".join(step.name.split())] if step.name else []
    heart_rate = targets.get("heart_rate")
    if heart_rate is not None:
        low, high = int(heart_rate.low), int(heart_rate.high)
        value = f"{low}" if low == high else f"{low}-{high}"
        cue.append(f"HR {value} bpm")
        warnings.append(
            f"Step '{step.type}': Zwift has no heart rate targets; {value} bpm kept "
            "in the step text"
        )
    if cue:
        ET.SubElement(element, "textevent", timeoffset="0", message=" - ".join(cue))
    return element


class ZwiftWorkoutAdapter(PayloadAdapter):
    @property
    def connector_name(self) -> str:
        return "zwift"

    def to_payload(self, plan: WorkoutPlan) -> AdapterResult:
        if plan.sport != "cycling":
            raise ValueError(f"Zwift workouts are rides; a {plan.sport} plan is not")
        warnings: list[str] = []
        root = ET.Element("workout_file")
        ET.SubElement(root, "author").text = "Training Plan Generator"
        ET.SubElement(root, "name").text = plan.name
        ET.SubElement(root, "description").text = plan.description
        ET.SubElement(root, "sportType").text = "bike"
        workout = ET.SubElement(root, "workout")
        for step in _flatten(plan.steps):
            workout.append(_element(step, plan.ftp_watts, warnings))
        ET.indent(root)
        content = ET.tostring(root, encoding="unicode") + "\n"
        # Repeated steps would otherwise repeat their warnings once per lap.
        unique = list(dict.fromkeys(warnings))
        return AdapterResult({"name": plan.name, "content": content}, unique)
