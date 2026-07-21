import pytest

from app.models.parser import parse_workout, parse_workout_file
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


def test_sport_list_raises():
    with pytest.raises(ValueError, match="sport"):
        parse_workout(_plan(sport=[]))


def test_sport_dict_raises():
    with pytest.raises(ValueError, match="sport"):
        parse_workout(_plan(sport={}))


def test_unknown_step_type_raises():
    data = _plan(steps=[{"type": "sprint", "duration_seconds": 300}])
    with pytest.raises(ValueError, match="step type"):
        parse_workout(data)


def test_step_type_list_raises():
    data = _plan(steps=[{"type": [], "duration_seconds": 60}])
    with pytest.raises(ValueError, match="step type"):
        parse_workout(data)


def test_step_type_dict_raises():
    data = _plan(steps=[{"type": {}, "duration_seconds": 60}])
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


def test_target_type_list_raises():
    data = _plan(
        steps=[
            {
                "type": "interval",
                "duration_seconds": 300,
                "targets": [{"type": [], "low": 100, "high": 200}],
            }
        ]
    )
    with pytest.raises(ValueError, match="target type"):
        parse_workout(data)


def test_target_type_dict_raises():
    data = _plan(
        steps=[
            {
                "type": "interval",
                "duration_seconds": 300,
                "targets": [{"type": {}, "low": 100, "high": 200}],
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


# --- duration_type ---


def test_duration_type_defaults_to_time():
    plan = parse_workout(_plan())
    assert plan.steps[0].duration_type == "time"


def test_duration_type_distance_accepted():
    data = _plan(
        steps=[
            {"type": "interval", "duration_seconds": 1000, "duration_type": "distance"}
        ]
    )
    plan = parse_workout(data)
    assert plan.steps[0].duration_type == "distance"
    assert plan.steps[0].duration_seconds == 1000


def test_duration_type_open_no_duration_accepted():
    data = _plan(steps=[{"type": "rest", "duration_type": "open"}])
    plan = parse_workout(data)
    assert plan.steps[0].duration_type == "open"
    assert plan.steps[0].duration_seconds is None


def test_duration_type_open_explicit_null_accepted():
    data = _plan(
        steps=[{"type": "rest", "duration_type": "open", "duration_seconds": None}]
    )
    plan = parse_workout(data)
    assert plan.steps[0].duration_seconds is None


def test_duration_type_open_zero_accepted():
    data = _plan(
        steps=[{"type": "rest", "duration_type": "open", "duration_seconds": 0}]
    )
    plan = parse_workout(data)
    assert plan.steps[0].duration_seconds is None


def test_duration_type_open_false_raises():
    data = _plan(
        steps=[{"type": "rest", "duration_type": "open", "duration_seconds": False}]
    )
    with pytest.raises(ValueError, match="got bool"):
        parse_workout(data)


def test_duration_type_open_positive_raises():
    data = _plan(
        steps=[{"type": "rest", "duration_type": "open", "duration_seconds": 60}]
    )
    with pytest.raises(ValueError, match="absent or null"):
        parse_workout(data)


def test_duration_type_invalid_raises():
    data = _plan(
        steps=[
            {"type": "interval", "duration_seconds": 300, "duration_type": "calories"}
        ]
    )
    with pytest.raises(ValueError, match="unknown duration_type"):
        parse_workout(data)


def test_duration_type_list_raises():
    data = _plan(
        steps=[{"type": "warmup", "duration_seconds": 60, "duration_type": []}]
    )
    with pytest.raises(ValueError, match="'duration_type' must be a string"):
        parse_workout(data)


def test_duration_type_dict_raises():
    data = _plan(
        steps=[{"type": "warmup", "duration_seconds": 60, "duration_type": {}}]
    )
    with pytest.raises(ValueError, match="'duration_type' must be a string"):
        parse_workout(data)


def test_duration_type_time_missing_duration_raises():
    data = _plan(steps=[{"type": "interval", "duration_type": "time"}])
    with pytest.raises(ValueError, match="duration_seconds"):
        parse_workout(data)


def test_duration_type_distance_missing_duration_raises():
    data = _plan(steps=[{"type": "interval", "duration_type": "distance"}])
    with pytest.raises(ValueError, match="duration_seconds"):
        parse_workout(data)


# --- step name ---


def test_plan_description_defaults_to_empty():
    plan = parse_workout(_plan())
    assert plan.description == ""


def test_plan_description_parsed():
    plan = parse_workout(_plan(description="Hard intervals"))
    assert plan.description == "Hard intervals"


def test_plan_description_nonstring_raises():
    with pytest.raises(ValueError, match="'description' must be a string"):
        parse_workout(_plan(description=123))


def test_plan_estimated_tss_defaults_to_none():
    plan = parse_workout(_plan())
    assert plan.estimated_tss is None


def test_plan_estimated_tss_parsed():
    plan = parse_workout(_plan(estimated_tss=85.5))
    assert plan.estimated_tss == 85.5


def test_plan_estimated_tss_zero_accepted():
    plan = parse_workout(_plan(estimated_tss=0))
    assert plan.estimated_tss == 0.0


def test_plan_estimated_tss_negative_raises():
    with pytest.raises(ValueError, match="non-negative"):
        parse_workout(_plan(estimated_tss=-1))


def test_plan_estimated_tss_nan_raises():
    with pytest.raises(ValueError, match="finite"):
        parse_workout(_plan(estimated_tss=float("nan")))


def test_plan_estimated_tss_inf_raises():
    with pytest.raises(ValueError, match="finite"):
        parse_workout(_plan(estimated_tss=float("inf")))


def test_plan_estimated_tss_string_raises():
    with pytest.raises(ValueError, match="non-negative number"):
        parse_workout(_plan(estimated_tss="high"))


def test_plan_estimated_tss_bool_raises():
    with pytest.raises(ValueError, match="got bool"):
        parse_workout(_plan(estimated_tss=True))


def test_plan_ftp_watts_defaults_to_none():
    plan = parse_workout(_plan())
    assert plan.ftp_watts is None


def test_plan_ftp_watts_parsed():
    plan = parse_workout(_plan(ftp_watts=280))
    assert plan.ftp_watts == 280


def test_plan_ftp_watts_integral_float_accepted():
    plan = parse_workout(_plan(ftp_watts=280.0))
    assert plan.ftp_watts == 280


def test_plan_ftp_watts_zero_raises():
    with pytest.raises(ValueError, match="positive"):
        parse_workout(_plan(ftp_watts=0))


def test_plan_ftp_watts_fractional_raises():
    with pytest.raises(ValueError, match="positive integer"):
        parse_workout(_plan(ftp_watts=100.5))


def test_plan_ftp_watts_bool_raises():
    with pytest.raises(ValueError, match="got bool"):
        parse_workout(_plan(ftp_watts=True))


def test_plan_ftp_watts_string_raises():
    with pytest.raises(ValueError, match="positive integer"):
        parse_workout(_plan(ftp_watts="280"))


def test_step_name_defaults_to_empty():
    plan = parse_workout(_plan())
    assert plan.steps[0].name == ""


def test_step_name_parsed():
    data = _plan(steps=[{"type": "warmup", "duration_seconds": 300, "name": "Warm Up"}])
    plan = parse_workout(data)
    assert plan.steps[0].name == "Warm Up"


def test_step_name_whitespace_stripped():
    data = _plan(steps=[{"type": "warmup", "duration_seconds": 300, "name": "  Z1  "}])
    plan = parse_workout(data)
    assert plan.steps[0].name == "Z1"


def test_step_name_whitespace_only_becomes_empty():
    data = _plan(steps=[{"type": "warmup", "duration_seconds": 300, "name": "   "}])
    plan = parse_workout(data)
    assert plan.steps[0].name == ""


def test_step_name_nonstring_raises():
    data = _plan(steps=[{"type": "warmup", "duration_seconds": 300, "name": 123}])
    with pytest.raises(ValueError, match="'name' must be a string"):
        parse_workout(data)


# --- target value ranges ---


def _step_with_typed_target(target_type, low, high):
    return _plan(
        steps=[
            {
                "type": "interval",
                "duration_seconds": 300,
                "targets": [{"type": target_type, "low": low, "high": high}],
            }
        ]
    )


@pytest.mark.parametrize(
    "target_type,low,high",
    [
        ("power", 0, 100),
        ("power", 2000, 2500),
        ("cadence", 0, 90),
        ("cadence", 80, 220),
        ("heart_rate", 20, 100),
        ("heart_rate", 100, 250),
    ],
)
def test_target_range_boundary_accepted(target_type, low, high):
    plan = parse_workout(_step_with_typed_target(target_type, low, high))
    assert plan.steps[0].targets[0].low == low


@pytest.mark.parametrize(
    "target_type,low,high",
    [
        ("power", -1, 100),
        ("power", 100, 2501),
        ("cadence", -1, 90),
        ("cadence", 80, 221),
        ("heart_rate", 19, 100),
        ("heart_rate", 100, 251),
    ],
)
def test_target_range_out_of_bounds_raises(target_type, low, high):
    with pytest.raises(ValueError, match="out of range"):
        parse_workout(_step_with_typed_target(target_type, low, high))


# --- repeat nesting depth ---


def test_single_level_repeat_accepted():
    data = _plan(
        steps=[
            {
                "type": "repeat",
                "count": 2,
                "steps": [{"type": "interval", "duration_seconds": 60}],
            }
        ]
    )
    plan = parse_workout(data)
    assert isinstance(plan.steps[0], RepeatStep)


def test_nested_repeat_raises():
    data = _plan(
        steps=[
            {
                "type": "repeat",
                "count": 2,
                "steps": [
                    {
                        "type": "repeat",
                        "count": 3,
                        "steps": [{"type": "interval", "duration_seconds": 60}],
                    }
                ],
            }
        ]
    )
    with pytest.raises(ValueError, match="Nested repeat"):
        parse_workout(data)


# --- parse_workout_file ---


def test_parse_workout_file_single_workout_object():
    result = parse_workout_file(_plan())
    assert len(result) == 1
    assert isinstance(result[0], WorkoutPlan)
    assert result[0].name == "Test Plan"


def test_parse_workout_file_list_format():
    data = [
        _plan(name="Morning Ride"),
        _plan(name="Evening Run", sport="running"),
    ]
    result = parse_workout_file(data)
    assert [p.name for p in result] == ["Morning Ride", "Evening Run"]
    assert result[1].sport == "running"


def test_parse_workout_file_list_preserves_order():
    data = [_plan(name="A"), _plan(name="B"), _plan(name="C")]
    assert [p.name for p in parse_workout_file(data)] == ["A", "B", "C"]


def test_parse_workout_file_list_single_entry():
    result = parse_workout_file([_plan(name="Solo")])
    assert len(result) == 1
    assert result[0].name == "Solo"


def test_parse_workout_file_list_allows_duplicate_names():
    result = parse_workout_file([_plan(name="Same"), _plan(name="Same")])
    assert len(result) == 2


def test_parse_workout_file_name_to_workout_mapping_gives_clear_error():
    """A name->workout mapping must name the real problem, not a missing 'name'."""
    data = {"training 1": _plan(name="Threshold 4x8")}
    with pytest.raises(ValueError, match="wrap the workouts in a JSON array"):
        parse_workout_file(data)


def test_parse_workout_file_mapping_error_mentions_neither_name_nor_nonetype():
    data = {"a": _plan(name="A"), "b": _plan(name="B")}
    with pytest.raises(ValueError) as excinfo:
        parse_workout_file(data)
    assert "NoneType" not in str(excinfo.value)


def test_parse_workout_file_single_workout_not_mistaken_for_mapping():
    """A real single workout has 'steps' at the top level - it must still parse."""
    result = parse_workout_file(_plan(name="Solo"))
    assert [p.name for p in result] == ["Solo"]


def test_parse_workout_file_dict_without_steps_still_reports_missing_steps():
    with pytest.raises(ValueError, match="steps"):
        parse_workout_file({"name": "X", "sport": "cycling"})


def test_parse_workout_file_scalar_raises():
    with pytest.raises(ValueError, match="JSON object or array"):
        parse_workout_file("not a plan")


def test_parse_workout_file_empty_list_raises():
    with pytest.raises(ValueError, match="must not be empty"):
        parse_workout_file([])


def test_parse_workout_file_list_invalid_workout_raises():
    data = [_plan(), {"name": "X", "sport": "cycling"}]  # second is missing steps
    with pytest.raises(ValueError, match="steps"):
        parse_workout_file(data)


def test_parse_workout_file_single_invalid_raises():
    with pytest.raises(ValueError, match="sport"):
        parse_workout_file(_plan(sport="golf"))


def test_triple_nested_repeat_raises():
    data = _plan(
        steps=[
            {
                "type": "repeat",
                "count": 2,
                "steps": [
                    {
                        "type": "repeat",
                        "count": 3,
                        "steps": [
                            {
                                "type": "repeat",
                                "count": 4,
                                "steps": [{"type": "interval", "duration_seconds": 60}],
                            }
                        ],
                    }
                ],
            }
        ]
    )
    with pytest.raises(ValueError, match="Nested repeat"):
        parse_workout(data)
