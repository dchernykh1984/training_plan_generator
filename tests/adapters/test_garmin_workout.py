import pytest

from app.adapters.garmin_workout import GarminWorkoutAdapter
from app.models.parser import parse_workout


def _plan(**overrides):
    base = {
        "name": "Test Plan",
        "sport": "cycling",
        "steps": [{"type": "warmup", "duration_seconds": 300}],
    }
    base.update(overrides)
    return base


def _adapter():
    return GarminWorkoutAdapter()


def _first_step(result):
    return result.payload["workoutSegments"][0]["workoutSteps"][0]


def test_connector_name():
    assert _adapter().connector_name == "garmin"


def test_warmup_step_type():
    plan = parse_workout(_plan(steps=[{"type": "warmup", "duration_seconds": 300}]))
    result = _adapter().to_payload(plan)
    step = _first_step(result)
    assert step["stepType"]["stepTypeKey"] == "warmup"
    assert step["type"] == "ExecutableStepDTO"


def test_cooldown_step_type():
    plan = parse_workout(_plan(steps=[{"type": "cooldown", "duration_seconds": 180}]))
    step = _first_step(_adapter().to_payload(plan))
    assert step["stepType"]["stepTypeKey"] == "cooldown"


def test_interval_step_type():
    plan = parse_workout(_plan(steps=[{"type": "interval", "duration_seconds": 480}]))
    step = _first_step(_adapter().to_payload(plan))
    assert step["stepType"]["stepTypeKey"] == "interval"


def test_rest_step_type():
    plan = parse_workout(_plan(steps=[{"type": "rest", "duration_seconds": 240}]))
    step = _first_step(_adapter().to_payload(plan))
    assert step["stepType"]["stepTypeKey"] == "rest"


def test_no_target_step():
    plan = parse_workout(_plan(steps=[{"type": "warmup", "duration_seconds": 300}]))
    step = _first_step(_adapter().to_payload(plan))
    assert step["targetType"]["workoutTargetTypeKey"] == "no.target"
    assert "secondaryTargetType" not in step


def test_single_power_target_primary_only():
    plan = parse_workout(
        _plan(
            steps=[
                {
                    "type": "interval",
                    "duration_seconds": 480,
                    "targets": [{"type": "power", "low": 260, "high": 300}],
                }
            ]
        )
    )
    result = _adapter().to_payload(plan)
    step = _first_step(result)
    assert step["targetType"]["workoutTargetTypeKey"] == "power.zone"
    assert step["targetValueOne"] == 260
    assert step["targetValueTwo"] == 300
    assert "secondaryTargetType" not in step
    assert result.warnings == []


def test_two_targets_primary_and_secondary():
    plan = parse_workout(
        _plan(
            steps=[
                {
                    "type": "interval",
                    "duration_seconds": 480,
                    "targets": [
                        {"type": "power", "low": 260, "high": 300},
                        {"type": "heart_rate", "low": 155, "high": 165},
                    ],
                }
            ]
        )
    )
    result = _adapter().to_payload(plan)
    step = _first_step(result)
    assert step["targetType"]["workoutTargetTypeKey"] == "power.zone"
    assert step["targetValueOne"] == 260
    assert step["secondaryTargetType"]["workoutTargetTypeKey"] == "heart.rate.zone"
    assert step["secondaryTargetValueOne"] == 155
    assert result.warnings == []


def test_three_targets_cadence_dropped_warning_in_result():
    plan = parse_workout(
        _plan(
            steps=[
                {
                    "type": "interval",
                    "duration_seconds": 480,
                    "targets": [
                        {"type": "power", "low": 260, "high": 300},
                        {"type": "cadence", "low": 88, "high": 92},
                        {"type": "heart_rate", "low": 155, "high": 165},
                    ],
                }
            ]
        )
    )
    result = _adapter().to_payload(plan)
    assert any("cadence dropped" in w for w in result.warnings)
    step = _first_step(result)
    assert step["targetType"]["workoutTargetTypeKey"] == "power.zone"
    assert step["secondaryTargetType"]["workoutTargetTypeKey"] == "heart.rate.zone"
    assert "cadence" not in str(step.get("secondaryTargetType", ""))


def test_priority_is_deterministic_regardless_of_input_order():
    plan = parse_workout(
        _plan(
            steps=[
                {
                    "type": "interval",
                    "duration_seconds": 480,
                    "targets": [
                        {"type": "cadence", "low": 88, "high": 92},
                        {"type": "heart_rate", "low": 155, "high": 165},
                        {"type": "power", "low": 260, "high": 300},
                    ],
                }
            ]
        )
    )
    result = _adapter().to_payload(plan)
    step = _first_step(result)
    assert step["targetType"]["workoutTargetTypeKey"] == "power.zone"
    assert step["secondaryTargetType"]["workoutTargetTypeKey"] == "heart.rate.zone"
    assert any("cadence dropped" in w for w in result.warnings)


def test_repeat_step_structure():
    plan = parse_workout(
        _plan(
            steps=[
                {
                    "type": "repeat",
                    "count": 3,
                    "steps": [
                        {"type": "interval", "duration_seconds": 480},
                        {"type": "rest", "duration_seconds": 240},
                    ],
                }
            ]
        )
    )
    result = _adapter().to_payload(plan)
    repeat = _first_step(result)
    assert repeat["type"] == "RepeatGroupDTO"
    assert repeat["stepType"]["stepTypeKey"] == "repeat"
    assert repeat["numberOfIterations"] == 3
    assert len(repeat["workoutSteps"]) == 2


def test_full_example_plan_payload():
    data = {
        "name": "3x8 Cycling Intervals",
        "sport": "cycling",
        "steps": [
            {
                "type": "warmup",
                "duration_seconds": 600,
                "targets": [{"type": "power", "low": 130, "high": 170}],
            },
            {
                "type": "repeat",
                "count": 3,
                "steps": [
                    {
                        "type": "interval",
                        "duration_seconds": 480,
                        "targets": [
                            {"type": "power", "low": 260, "high": 300},
                            {"type": "cadence", "low": 88, "high": 92},
                            {"type": "heart_rate", "low": 155, "high": 165},
                        ],
                    },
                    {
                        "type": "rest",
                        "duration_seconds": 240,
                        "targets": [
                            {"type": "power", "low": 90, "high": 110},
                            {"type": "cadence", "low": 65, "high": 75},
                            {"type": "heart_rate", "low": 110, "high": 130},
                        ],
                    },
                ],
            },
            {
                "type": "cooldown",
                "duration_seconds": 300,
                "targets": [{"type": "power", "low": 90, "high": 120}],
            },
        ],
    }
    plan = parse_workout(data)
    result = _adapter().to_payload(plan)
    payload = result.payload

    assert payload["workoutName"] == "3x8 Cycling Intervals"
    assert payload["sportType"]["sportTypeKey"] == "cycling"
    assert payload["sportType"]["sportTypeId"] == 2
    assert payload["estimatedDurationInSecs"] == 600 + 3 * (480 + 240) + 300

    outer_steps = payload["workoutSegments"][0]["workoutSteps"]
    assert len(outer_steps) == 3

    warmup = outer_steps[0]
    assert warmup["stepType"]["stepTypeKey"] == "warmup"
    assert warmup["targetType"]["workoutTargetTypeKey"] == "power.zone"

    repeat = outer_steps[1]
    assert repeat["stepType"]["stepTypeKey"] == "repeat"
    assert repeat["numberOfIterations"] == 3

    cooldown = outer_steps[2]
    assert cooldown["stepType"]["stepTypeKey"] == "cooldown"


def test_heart_rate_target_type_mapping():
    plan = parse_workout(
        _plan(
            steps=[
                {
                    "type": "interval",
                    "duration_seconds": 300,
                    "targets": [{"type": "heart_rate", "low": 150, "high": 165}],
                }
            ]
        )
    )
    step = _first_step(_adapter().to_payload(plan))
    assert step["targetType"]["workoutTargetTypeKey"] == "heart.rate.zone"


def test_cadence_target_type_mapping():
    plan = parse_workout(
        _plan(
            steps=[
                {
                    "type": "interval",
                    "duration_seconds": 300,
                    "targets": [{"type": "cadence", "low": 85, "high": 95}],
                }
            ]
        )
    )
    step = _first_step(_adapter().to_payload(plan))
    assert step["targetType"]["workoutTargetTypeKey"] == "cadence"


@pytest.mark.parametrize(
    "targets,expected_primary,expected_secondary",
    [
        (
            [{"type": "power", "low": 200, "high": 250}],
            "power.zone",
            None,
        ),
        (
            [
                {"type": "heart_rate", "low": 150, "high": 165},
                {"type": "cadence", "low": 85, "high": 95},
            ],
            "heart.rate.zone",
            "cadence",
        ),
    ],
)
def test_target_priority_parametrized(targets, expected_primary, expected_secondary):
    plan = parse_workout(
        _plan(
            steps=[
                {
                    "type": "interval",
                    "duration_seconds": 300,
                    "targets": targets,
                }
            ]
        )
    )
    result = _adapter().to_payload(plan)
    step = _first_step(result)
    assert step["targetType"]["workoutTargetTypeKey"] == expected_primary
    if expected_secondary:
        assert step["secondaryTargetType"]["workoutTargetTypeKey"] == expected_secondary
    else:
        assert "secondaryTargetType" not in step


def test_step_order_in_flat_steps():
    plan = parse_workout(
        _plan(
            steps=[
                {"type": "warmup", "duration_seconds": 300},
                {"type": "interval", "duration_seconds": 480},
                {"type": "cooldown", "duration_seconds": 180},
            ]
        )
    )
    steps = _adapter().to_payload(plan).payload["workoutSegments"][0]["workoutSteps"]
    assert [s["stepOrder"] for s in steps] == [1, 2, 3]


def test_step_order_inside_repeat_starts_from_one():
    plan = parse_workout(
        _plan(
            steps=[
                {
                    "type": "repeat",
                    "count": 2,
                    "steps": [
                        {"type": "interval", "duration_seconds": 300},
                        {"type": "rest", "duration_seconds": 120},
                    ],
                }
            ]
        )
    )
    repeat = _first_step(_adapter().to_payload(plan))
    inner_orders = [s["stepOrder"] for s in repeat["workoutSteps"]]
    assert inner_orders == [1, 2]


def test_estimated_duration_flat_steps():
    plan = parse_workout(
        _plan(
            steps=[
                {"type": "warmup", "duration_seconds": 600},
                {"type": "cooldown", "duration_seconds": 300},
            ]
        )
    )
    payload = _adapter().to_payload(plan).payload
    assert payload["estimatedDurationInSecs"] == 900


def test_estimated_duration_with_repeat():
    plan = parse_workout(
        _plan(
            steps=[
                {
                    "type": "repeat",
                    "count": 3,
                    "steps": [
                        {"type": "interval", "duration_seconds": 480},
                        {"type": "rest", "duration_seconds": 240},
                    ],
                }
            ]
        )
    )
    payload = _adapter().to_payload(plan).payload
    assert payload["estimatedDurationInSecs"] == 3 * (480 + 240)


def test_sport_type_has_id_and_key():
    plan = parse_workout(_plan(sport="running"))
    payload = _adapter().to_payload(plan).payload
    assert payload["sportType"]["sportTypeId"] == 1
    assert payload["sportType"]["sportTypeKey"] == "running"
    segment_sport = payload["workoutSegments"][0]["sportType"]
    assert segment_sport == payload["sportType"]


def test_segment_contains_sport_type():
    plan = parse_workout(_plan())
    payload = _adapter().to_payload(plan).payload
    segment = payload["workoutSegments"][0]
    assert "sportType" in segment
    assert segment["sportType"]["sportTypeId"] == 2


def test_duration_type_time_end_condition():
    plan = parse_workout(_plan(steps=[{"type": "interval", "duration_seconds": 300}]))
    step = _first_step(_adapter().to_payload(plan))
    assert step["endCondition"]["conditionTypeKey"] == "time"
    assert step["endConditionValue"] == 300.0


def test_duration_type_distance_end_condition():
    plan = parse_workout(
        _plan(
            steps=[
                {
                    "type": "interval",
                    "duration_seconds": 1000,
                    "duration_type": "distance",
                }
            ]
        )
    )
    step = _first_step(_adapter().to_payload(plan))
    assert step["endCondition"]["conditionTypeKey"] == "distance"
    assert step["endConditionValue"] == 1000.0


def test_duration_type_open_end_condition():
    plan = parse_workout(_plan(steps=[{"type": "rest", "duration_type": "open"}]))
    step = _first_step(_adapter().to_payload(plan))
    assert step["endCondition"]["conditionTypeKey"] == "lap.button"
    assert step["endConditionValue"] is None


def test_total_duration_excludes_open_steps():
    plan = parse_workout(
        _plan(
            steps=[
                {"type": "warmup", "duration_seconds": 600},
                {"type": "rest", "duration_type": "open"},
                {"type": "cooldown", "duration_seconds": 300},
            ]
        )
    )
    payload = _adapter().to_payload(plan).payload
    assert payload["estimatedDurationInSecs"] == 900


def test_total_duration_excludes_distance_steps():
    plan = parse_workout(
        _plan(
            steps=[
                {"type": "warmup", "duration_seconds": 600},
                {
                    "type": "interval",
                    "duration_seconds": 1000,
                    "duration_type": "distance",
                },
                {"type": "cooldown", "duration_seconds": 300},
            ]
        )
    )
    payload = _adapter().to_payload(plan).payload
    assert payload["estimatedDurationInSecs"] == 900


def test_expanded_step_count_below_limit_no_warning():
    steps = [{"type": "interval", "duration_seconds": 60}] * 5
    plan = parse_workout(_plan(steps=steps))
    result = _adapter().to_payload(plan)
    assert not any("exceeds Garmin limit" in w for w in result.warnings)


def test_expanded_step_count_exactly_limit_no_warning():
    steps = [
        {
            "type": "repeat",
            "count": 10,
            "steps": [
                {"type": "interval", "duration_seconds": 60},
                {"type": "rest", "duration_seconds": 30},
                {"type": "cooldown", "duration_seconds": 30},
                {"type": "warmup", "duration_seconds": 30},
                {"type": "interval", "duration_seconds": 60},
            ],
        }
    ]
    plan = parse_workout(_plan(steps=steps))
    result = _adapter().to_payload(plan)
    assert not any("exceeds Garmin limit" in w for w in result.warnings)


def test_expanded_step_count_exceeds_limit_warning():
    steps = [
        {
            "type": "repeat",
            "count": 11,
            "steps": [
                {"type": "interval", "duration_seconds": 60},
                {"type": "rest", "duration_seconds": 30},
                {"type": "cooldown", "duration_seconds": 30},
                {"type": "warmup", "duration_seconds": 30},
                {"type": "interval", "duration_seconds": 60},
            ],
        }
    ]
    plan = parse_workout(_plan(steps=steps))
    result = _adapter().to_payload(plan)
    assert any("exceeds Garmin limit" in w for w in result.warnings)


def test_step_description_present_when_name_set():
    plan = parse_workout(
        _plan(steps=[{"type": "warmup", "duration_seconds": 300, "name": "Z1 Warm Up"}])
    )
    step = _first_step(_adapter().to_payload(plan))
    assert step["stepDescription"] == "Z1 Warm Up"


def test_step_description_absent_when_name_empty():
    plan = parse_workout(_plan(steps=[{"type": "warmup", "duration_seconds": 300}]))
    step = _first_step(_adapter().to_payload(plan))
    assert "stepDescription" not in step
