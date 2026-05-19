from __future__ import annotations

from app.adapters.base import AdapterResult, PayloadAdapter
from app.models.workout import RepeatStep, Target, WorkoutPlan, WorkoutStep

_SPORT_TYPE: dict[str, dict] = {
    "cycling": {"sportTypeId": 2, "sportTypeKey": "cycling", "displayOrder": 2},
    "running": {"sportTypeId": 1, "sportTypeKey": "running", "displayOrder": 1},
    "swimming": {"sportTypeId": 4, "sportTypeKey": "swimming", "displayOrder": 3},
}

_STEP_TYPE: dict[str, dict] = {
    "warmup": {"stepTypeId": 1, "stepTypeKey": "warmup", "displayOrder": 1},
    "cooldown": {"stepTypeId": 2, "stepTypeKey": "cooldown", "displayOrder": 2},
    "interval": {"stepTypeId": 3, "stepTypeKey": "interval", "displayOrder": 3},
    "rest": {"stepTypeId": 5, "stepTypeKey": "rest", "displayOrder": 5},
}

_TARGET_TYPE: dict[str, dict] = {
    "power": {
        "workoutTargetTypeId": 2,
        "workoutTargetTypeKey": "power.zone",
        "displayOrder": 1,
    },
    "heart_rate": {
        "workoutTargetTypeId": 4,
        "workoutTargetTypeKey": "heart.rate.zone",
        "displayOrder": 1,
    },
    "cadence": {
        "workoutTargetTypeId": 3,
        "workoutTargetTypeKey": "cadence",
        "displayOrder": 1,
    },
}

_NO_TARGET: dict = {
    "workoutTargetTypeId": 1,
    "workoutTargetTypeKey": "no.target",
    "displayOrder": 1,
}

_END_CONDITION_BY_TYPE: dict[str, dict] = {
    "time": {
        "conditionTypeId": 2,
        "conditionTypeKey": "time",
        "displayOrder": 2,
        "displayable": True,
    },
    "distance": {
        "conditionTypeId": 3,
        "conditionTypeKey": "distance",
        "displayOrder": 3,
        "displayable": True,
    },
    "open": {
        "conditionTypeId": 1,
        "conditionTypeKey": "lap.button",
        "displayOrder": 1,
        "displayable": True,
    },
}

_TARGET_PRIORITY: list[str] = ["power", "heart_rate", "cadence"]
_GARMIN_MAX_STEPS = 50
_GARMIN_MAX_TARGETS = 2


def _count_expanded(steps: tuple) -> int:
    total = 0
    for step in steps:
        if isinstance(step, RepeatStep):
            total += step.count * _count_expanded(step.steps)
        else:
            total += 1
    return total


def _sort_targets(targets: tuple[Target, ...]) -> list[Target]:
    return sorted(
        targets,
        key=lambda t: (
            _TARGET_PRIORITY.index(t.type) if t.type in _TARGET_PRIORITY else 99
        ),
    )


def _target_fields(prefix: str, target: Target) -> dict:
    target_type_dict = _TARGET_TYPE.get(target.type, _NO_TARGET)
    return {
        f"{prefix}Type": target_type_dict,
        f"{prefix}ValueOne": int(target.low),
        f"{prefix}ValueTwo": int(target.high),
    }


def _build_step_payload(
    step: WorkoutStep, step_order: int, warnings: list[str]
) -> dict:
    ordered = _sort_targets(step.targets)
    if len(ordered) > _GARMIN_MAX_TARGETS:
        dropped = ordered[_GARMIN_MAX_TARGETS:]
        kept = [t.type for t in ordered[:_GARMIN_MAX_TARGETS]]
        for drop in dropped:
            warnings.append(
                f"Step '{step.type}': Garmin supports {_GARMIN_MAX_TARGETS} targets; "
                f"{drop.type} dropped ({', '.join(kept)} kept)"
            )
        ordered = ordered[:_GARMIN_MAX_TARGETS]

    end_condition = _END_CONDITION_BY_TYPE.get(
        step.duration_type, _END_CONDITION_BY_TYPE["time"]
    )
    end_value = (
        float(step.duration_seconds) if step.duration_seconds is not None else None
    )
    payload: dict = {
        "type": "ExecutableStepDTO",
        "stepOrder": step_order,
        "stepType": _STEP_TYPE.get(step.type, _STEP_TYPE["interval"]),
        "endCondition": end_condition,
        "endConditionValue": end_value,
    }
    if step.name:
        payload["stepDescription"] = step.name

    if ordered:
        payload.update(_target_fields("target", ordered[0]))
    else:
        payload["targetType"] = _NO_TARGET

    if len(ordered) == 2:
        payload.update(_target_fields("secondaryTarget", ordered[1]))

    return payload


def _build_steps_payload(
    steps: tuple[WorkoutStep | RepeatStep, ...],
    counter: list[int],
    warnings: list[str],
) -> list[dict]:
    result = []
    for step in steps:
        step_order = counter[0]
        counter[0] += 1
        if isinstance(step, RepeatStep):
            inner_counter = [1]
            inner_steps = _build_steps_payload(step.steps, inner_counter, warnings)
            result.append(
                {
                    "type": "RepeatGroupDTO",
                    "stepOrder": step_order,
                    "stepType": {
                        "stepTypeId": 6,
                        "stepTypeKey": "repeat",
                        "displayOrder": 6,
                    },
                    "numberOfIterations": step.count,
                    "workoutSteps": inner_steps,
                    "endCondition": {
                        "conditionTypeId": 7,
                        "conditionTypeKey": "iterations",
                        "displayOrder": 7,
                        "displayable": False,
                    },
                    "endConditionValue": float(step.count),
                }
            )
        else:
            result.append(_build_step_payload(step, step_order, warnings))
    return result


def _total_duration(steps: tuple) -> int:
    total = 0
    for step in steps:
        if isinstance(step, RepeatStep):
            total += step.count * _total_duration(step.steps)
        elif step.duration_type == "time" and step.duration_seconds is not None:
            total += step.duration_seconds
    return total


class GarminWorkoutAdapter(PayloadAdapter):
    @property
    def connector_name(self) -> str:
        return "garmin"

    def to_payload(self, plan: WorkoutPlan) -> AdapterResult:
        warnings: list[str] = []
        expanded = _count_expanded(plan.steps)
        if expanded > _GARMIN_MAX_STEPS:
            warnings.append(
                f"Expanded step count {expanded} exceeds Garmin limit "
                f"of {_GARMIN_MAX_STEPS} steps"
            )
        sport = _SPORT_TYPE.get(
            plan.sport,
            {"sportTypeId": 8, "sportTypeKey": plan.sport, "displayOrder": 8},
        )
        counter = [1]
        steps = _build_steps_payload(plan.steps, counter, warnings)
        payload: dict = {
            "workoutName": plan.name,
            "sportType": sport,
            "estimatedDurationInSecs": _total_duration(plan.steps),
            "workoutSegments": [
                {
                    "segmentOrder": 1,
                    "sportType": sport,
                    "workoutSteps": steps,
                }
            ],
        }
        if plan.description:
            payload["description"] = plan.description
        return AdapterResult(payload=payload, warnings=warnings)
