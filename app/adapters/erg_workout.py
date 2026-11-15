"""WorkoutPlan -> ERG file: the ride's power in watts over time.

TrainerRoad, ROUVY, Xert and Golden Cheetah import ERG files. The format holds
nothing but power, so step names, cadence and heart rate are left out of it.
"""

from __future__ import annotations

from app.adapters.base import (
    AdapterResult,
    PayloadAdapter,
    flatten_steps,
    middle,
    timed_seconds,
)
from app.models.workout import WorkoutPlan


def _one_line(text: str) -> str:
    return " ".join(text.split())


class ErgWorkoutAdapter(PayloadAdapter):
    @property
    def connector_name(self) -> str:
        return "erg-file"

    def to_payload(self, plan: WorkoutPlan) -> AdapterResult:
        if plan.sport != "cycling":
            raise ValueError(f"ERG files are rides; a {plan.sport} plan is not")
        warnings: list[str] = []
        rows: list[str] = []
        elapsed = 0
        for step in flatten_steps(plan.steps):
            seconds = timed_seconds(step, "ERG", warnings)
            power = next((t for t in step.targets if t.type == "power"), None)
            if power is None:
                warnings.append(
                    f"Step '{step.type}': ERG files need power; a step without a "
                    "power target is set to 0 W"
                )
                watts = 0
            else:
                watts = round(middle(power))
                if power.low != power.high:
                    warnings.append(
                        "ERG files hold one power per step; each power range is set "
                        "to its middle"
                    )
            if step.name or any(t.type != "power" for t in step.targets):
                warnings.append(
                    "ERG files hold only power; step names, cadence and heart rate "
                    "are left out"
                )
            # Two points per step draw it as a flat block on the power graph.
            rows.append(f"{elapsed / 60:.2f}\t{watts}")
            elapsed += seconds
            rows.append(f"{elapsed / 60:.2f}\t{watts}")
        lines = [
            "[COURSE HEADER]",
            "VERSION = 2",
            "UNITS = ENGLISH",
            f"DESCRIPTION = {_one_line(plan.description)}",
            f"FILE NAME = {_one_line(plan.name)}",
            "MINUTES WATTS",
            "[END COURSE HEADER]",
            "[COURSE DATA]",
            *rows,
            "[END COURSE DATA]",
        ]
        content = "\n".join(lines) + "\n"
        # Repeated steps would otherwise repeat their warnings once per lap.
        unique = list(dict.fromkeys(warnings))
        return AdapterResult({"name": plan.name, "content": content}, unique)
