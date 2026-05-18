import pytest

from app.models.parser import parse_workout
from app.models.workout import RepeatStep, Target, WorkoutPlan, WorkoutStep


def _plan(**overrides):
    base = {
        "name": "Test Plan",
        "sport": "cycling",
        "steps": [{"type": "warmup", "duration_seconds": 300}],
    }
    base.update(overrides)
    return base


def test_valid_plan_no_targets():
    plan = parse_workout(_plan())
    assert isinstance(plan, WorkoutPlan)
    step = plan.steps[0]
    assert isinstance(step, WorkoutStep)
    assert step.targets == ()


def test_valid_plan_one_target():
    data = _plan(
        steps=[
            {
                "type": "interval",
                "duration_seconds": 300,
                "targets": [{"type": "power", "low": 200, "high": 250}],
            }
        ]
    )
    plan = parse_workout(data)
    step = plan.steps[0]
    assert len(step.targets) == 1
    assert step.targets[0] == Target(type="power", low=200.0, high=250.0)


def test_valid_plan_two_targets():
    data = _plan(
        sport="running",
        steps=[
            {
                "type": "interval",
                "duration_seconds": 300,
                "targets": [
                    {"type": "heart_rate", "low": 150, "high": 165},
                    {"type": "cadence", "low": 80, "high": 90},
                ],
            }
        ],
    )
    plan = parse_workout(data)
    assert len(plan.steps[0].targets) == 2


def test_valid_plan_three_targets():
    data = _plan(
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
    plan = parse_workout(data)
    assert len(plan.steps[0].targets) == 3


def test_duplicate_target_type_raises():
    data = _plan(
        steps=[
            {
                "type": "interval",
                "duration_seconds": 300,
                "targets": [
                    {"type": "power", "low": 200, "high": 250},
                    {"type": "power", "low": 210, "high": 260},
                ],
            }
        ]
    )
    with pytest.raises(ValueError, match="duplicate target type"):
        parse_workout(data)


def test_invalid_sport_raises():
    with pytest.raises(ValueError, match="sport"):
        parse_workout(_plan(sport="skateboarding"))


def test_unknown_step_type_raises():
    data = _plan(steps=[{"type": "sprint", "duration_seconds": 300}])
    with pytest.raises(ValueError, match="step type"):
        parse_workout(data)


def test_missing_duration_raises():
    data = _plan(steps=[{"type": "interval"}])
    with pytest.raises(ValueError, match="duration_seconds"):
        parse_workout(data)


def test_missing_name_raises():
    data = _plan()
    del data["name"]
    with pytest.raises(ValueError, match="name"):
        parse_workout(data)


def test_name_not_string_raises():
    with pytest.raises(ValueError, match="'name' must be a string"):
        parse_workout(_plan(name=123))


def test_name_whitespace_only_raises():
    with pytest.raises(ValueError, match="whitespace"):
        parse_workout(_plan(name="   "))


def test_missing_steps_raises():
    data = _plan()
    del data["steps"]
    with pytest.raises(ValueError, match="steps"):
        parse_workout(data)


def test_unknown_target_type_raises():
    data = _plan(
        steps=[
            {
                "type": "interval",
                "duration_seconds": 300,
                "targets": [{"type": "pace", "low": 4.0, "high": 5.0}],
            }
        ]
    )
    with pytest.raises(ValueError, match="target type"):
        parse_workout(data)


def test_target_missing_low_raises():
    data = _plan(
        steps=[
            {
                "type": "interval",
                "duration_seconds": 300,
                "targets": [{"type": "power", "high": 250}],
            }
        ]
    )
    with pytest.raises(ValueError, match="low"):
        parse_workout(data)


def test_target_missing_high_raises():
    data = _plan(
        steps=[
            {
                "type": "interval",
                "duration_seconds": 300,
                "targets": [{"type": "power", "low": 200}],
            }
        ]
    )
    with pytest.raises(ValueError, match="high"):
        parse_workout(data)


def test_repeat_step_accepted():
    data = _plan(
        name="3x8 Intervals",
        steps=[
            {
                "type": "repeat",
                "count": 3,
                "steps": [
                    {
                        "type": "interval",
                        "duration_seconds": 480,
                        "targets": [{"type": "power", "low": 260, "high": 300}],
                    },
                    {
                        "type": "rest",
                        "duration_seconds": 240,
                        "targets": [{"type": "heart_rate", "low": 110, "high": 130}],
                    },
                ],
            }
        ],
    )
    plan = parse_workout(data)
    repeat = plan.steps[0]
    assert isinstance(repeat, RepeatStep)
    assert repeat.count == 3
    assert len(repeat.steps) == 2
    interval = repeat.steps[0]
    assert isinstance(interval, WorkoutStep)
    assert interval.type == "interval"
    assert len(interval.targets) == 1


def test_repeat_step_missing_count_raises():
    data = _plan(
        steps=[
            {"type": "repeat", "steps": [{"type": "interval", "duration_seconds": 300}]}
        ]
    )
    with pytest.raises(ValueError, match="count"):
        parse_workout(data)


def test_repeat_step_missing_steps_raises():
    data = _plan(steps=[{"type": "repeat", "count": 3}])
    with pytest.raises(ValueError, match="steps"):
        parse_workout(data)


def test_all_step_types_accepted():
    for step_type in ("warmup", "cooldown", "interval", "rest"):
        data = _plan(steps=[{"type": step_type, "duration_seconds": 60}])
        plan = parse_workout(data)
        assert plan.steps[0].type == step_type


def test_all_sport_types_accepted():
    for sport in ("cycling", "running", "swimming"):
        plan = parse_workout(_plan(sport=sport))
        assert plan.sport == sport


def test_full_example_plan():
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
    assert plan.name == "3x8 Cycling Intervals"
    assert plan.sport == "cycling"
    assert len(plan.steps) == 3
    warmup = plan.steps[0]
    assert isinstance(warmup, WorkoutStep)
    assert warmup.type == "warmup"
    assert warmup.duration_seconds == 600
    repeat = plan.steps[1]
    assert isinstance(repeat, RepeatStep)
    assert repeat.count == 3
    interval = repeat.steps[0]
    assert len(interval.targets) == 3


# --- shape / type validation ---


def test_plan_not_a_dict_raises():
    with pytest.raises(ValueError, match="JSON object"):
        parse_workout(["not", "a", "dict"])


def test_plan_steps_not_a_list_raises():
    with pytest.raises(ValueError, match="steps"):
        parse_workout(_plan(steps={"type": "warmup", "duration_seconds": 300}))


def test_step_not_a_dict_raises():
    data = _plan(steps=["not_a_step"])
    with pytest.raises(ValueError, match="step must be an object"):
        parse_workout(data)


def test_target_not_a_dict_raises():
    data = _plan(
        steps=[
            {
                "type": "interval",
                "duration_seconds": 300,
                "targets": ["not_a_target"],
            }
        ]
    )
    with pytest.raises(ValueError, match="target must be an object"):
        parse_workout(data)


def test_targets_not_a_list_raises():
    data = _plan(
        steps=[
            {
                "type": "interval",
                "duration_seconds": 300,
                "targets": {"type": "power", "low": 200, "high": 250},
            }
        ]
    )
    with pytest.raises(ValueError, match="'targets' must be a list"):
        parse_workout(data)


def test_repeat_steps_not_a_list_raises():
    data = _plan(steps=[{"type": "repeat", "count": 3, "steps": "not_a_list"}])
    with pytest.raises(ValueError, match="'steps' must be a list"):
        parse_workout(data)


# --- value validation ---


def test_duration_zero_raises():
    data = _plan(steps=[{"type": "warmup", "duration_seconds": 0}])
    with pytest.raises(ValueError, match=r"duration_seconds.*positive"):
        parse_workout(data)


def test_duration_negative_raises():
    data = _plan(steps=[{"type": "interval", "duration_seconds": -60}])
    with pytest.raises(ValueError, match=r"duration_seconds.*positive"):
        parse_workout(data)


def test_repeat_count_zero_raises():
    data = _plan(
        steps=[
            {
                "type": "repeat",
                "count": 0,
                "steps": [{"type": "interval", "duration_seconds": 60}],
            }
        ]
    )
    with pytest.raises(ValueError, match="'count' must be positive"):
        parse_workout(data)


def test_repeat_count_non_numeric_raises():
    data = _plan(
        steps=[
            {
                "type": "repeat",
                "count": "many",
                "steps": [{"type": "interval", "duration_seconds": 60}],
            }
        ]
    )
    with pytest.raises(ValueError, match="'count' must be a positive integer"):
        parse_workout(data)


def test_duration_non_numeric_raises():
    data = _plan(steps=[{"type": "warmup", "duration_seconds": "long"}])
    with pytest.raises(
        ValueError, match="'duration_seconds' must be a positive integer"
    ):
        parse_workout(data)


def test_duration_fractional_raises():
    data = _plan(steps=[{"type": "warmup", "duration_seconds": 1.9}])
    with pytest.raises(ValueError, match=r"positive integer, got 1\.9"):
        parse_workout(data)


def test_duration_boolean_raises():
    data = _plan(steps=[{"type": "warmup", "duration_seconds": True}])
    with pytest.raises(ValueError, match="got bool"):
        parse_workout(data)


def test_repeat_count_fractional_raises():
    data = _plan(
        steps=[
            {
                "type": "repeat",
                "count": 2.9,
                "steps": [{"type": "interval", "duration_seconds": 60}],
            }
        ]
    )
    with pytest.raises(ValueError, match=r"positive integer, got 2\.9"):
        parse_workout(data)


def test_repeat_count_boolean_raises():
    data = _plan(
        steps=[
            {
                "type": "repeat",
                "count": True,
                "steps": [{"type": "interval", "duration_seconds": 60}],
            }
        ]
    )
    with pytest.raises(ValueError, match="got bool"):
        parse_workout(data)


def test_target_low_greater_than_high_raises():
    data = _plan(
        steps=[
            {
                "type": "interval",
                "duration_seconds": 300,
                "targets": [{"type": "power", "low": 300, "high": 200}],
            }
        ]
    )
    with pytest.raises(ValueError, match=r"low=.*> high="):
        parse_workout(data)


def test_target_non_numeric_low_raises():
    data = _plan(
        steps=[
            {
                "type": "interval",
                "duration_seconds": 300,
                "targets": [{"type": "power", "low": "fast", "high": 250}],
            }
        ]
    )
    with pytest.raises(ValueError, match="numeric"):
        parse_workout(data)


def _step_with_target(low, high):
    return _plan(
        steps=[
            {
                "type": "interval",
                "duration_seconds": 300,
                "targets": [{"type": "power", "low": low, "high": high}],
            }
        ]
    )


def test_target_nan_low_raises():
    with pytest.raises(ValueError, match="finite"):
        parse_workout(_step_with_target(float("nan"), 200))


def test_target_nan_high_raises():
    with pytest.raises(ValueError, match="finite"):
        parse_workout(_step_with_target(100, float("nan")))


def test_target_infinity_raises():
    with pytest.raises(ValueError, match="finite"):
        parse_workout(_step_with_target(float("inf"), 200))


def test_target_negative_infinity_raises():
    with pytest.raises(ValueError, match="finite"):
        parse_workout(_step_with_target(100, float("-inf")))


def test_target_boolean_low_raises():
    with pytest.raises(ValueError, match="got bool"):
        parse_workout(_step_with_target(True, 200))


def test_target_boolean_high_raises():
    with pytest.raises(ValueError, match="got bool"):
        parse_workout(_step_with_target(100, False))


def test_target_fractional_low_raises():
    with pytest.raises(ValueError, match="whole numbers"):
        parse_workout(_step_with_target(200.9, 250))


def test_target_fractional_high_raises():
    with pytest.raises(ValueError, match="whole numbers"):
        parse_workout(_step_with_target(200, 250.9))


def test_target_integral_float_accepted():
    plan = parse_workout(_step_with_target(200.0, 250.0))
    assert plan.steps[0].targets[0].low == 200.0
    assert plan.steps[0].targets[0].high == 250.0
