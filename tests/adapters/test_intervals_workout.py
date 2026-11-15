import json
from pathlib import Path

import pytest

from app.adapters.intervals_workout import (
    _SPORT_TYPE,
    _UNITS,
    IntervalsWorkoutAdapter,
)
from app.models.parser import parse_workout
from app.models.workout import (
    SUPPORTED_SPORTS,
    SUPPORTED_TARGET_TYPES,
    RepeatStep,
    WorkoutPlan,
    WorkoutStep,
)

_EXAMPLE = Path(__file__).parents[2] / "examples" / "cycling_intervals.json"


def _payload(steps, **plan_fields):
    plan = parse_workout(
        {"name": "T", "sport": "cycling", "steps": steps, **plan_fields}
    )
    return IntervalsWorkoutAdapter().to_payload(plan)


def test_connector_name():
    assert IntervalsWorkoutAdapter().connector_name == "intervals"


def test_example_plan_becomes_intervals_workout_text():
    plan = parse_workout(json.loads(_EXAMPLE.read_text()))
    result = IntervalsWorkoutAdapter().to_payload(plan)

    assert result.payload == {
        "name": "3x8 Cycling Intervals",
        "type": "Ride",
        "description": (
            "VO2max build block: 3 sets of 8-minute efforts at 105-115% FTP\n"
            "\n"
            "- Easy Spin<!> 10m 130-170w intensity=warmup\n"
            "- 1km Build<!> 1000mtr 200-240w intensity=interval\n"
            "\n"
            "3x\n"
            "- 8min Effort HR 155-165 bpm<!> 8m 260-300w 88-92rpm intensity=interval\n"
            "- Active Recovery HR 110-130 bpm<!> 5m press lap intensity=rest\n"
            "\n"
            "- Easy Spin Down<!> 5m 90-120w intensity=cooldown"
        ),
    }
    assert result.warnings == [
        "Step 'interval': intervals.icu has no absolute heart rate targets; "
        "155-165 bpm kept in the step text",
        "Step 'rest': intervals.icu needs a duration; open step planned as 5m, "
        "ends on lap press",
        "Step 'rest': intervals.icu has no absolute heart rate targets; "
        "110-130 bpm kept in the step text",
    ]


@pytest.mark.parametrize(
    ("seconds", "token"),
    [(45, "45s"), (90, "1m30s"), (600, "10m"), (3600, "1h"), (3750, "1h2m30s")],
)
def test_time_duration_tokens(seconds, token):
    result = _payload([{"type": "interval", "duration_seconds": seconds}])
    assert result.payload["description"] == f"- {token} intensity=interval"


def test_equal_low_and_high_is_a_single_value():
    target = {"type": "power", "low": 250, "high": 250}
    result = _payload(
        [{"type": "interval", "duration_seconds": 60, "targets": [target]}]
    )
    assert result.payload["description"] == "- 1m 250w intensity=interval"
    assert result.warnings == []


def test_name_is_collapsed_onto_the_step_line():
    result = _payload(
        [{"type": "rest", "name": "Spin\n  easy", "duration_seconds": 60}]
    )
    assert result.payload["description"] == "- Spin easy<!> 1m intensity=rest"


@pytest.mark.parametrize(
    ("name", "cue"),
    [
        ("1. Warm-up", "1.Warm-up"),
        ("2) Main set", "2)Main set"),
        ("- easy spin", "-easy spin"),
        ("1.5km tempo", "1.5km tempo"),
    ],
)
def test_list_like_step_name_stays_in_its_step(name, cue):
    result = _payload([{"type": "warmup", "name": name, "duration_seconds": 60}])
    assert result.payload["description"] == f"- {cue}<!> 1m intensity=warmup"


def test_plan_description_is_collapsed_onto_one_line():
    # A "- 2m easy" line of its own would otherwise parse as an extra step.
    result = _payload(
        [{"type": "warmup", "duration_seconds": 60}],
        description="Notes:\n- 2m easy between sets",
    )
    assert result.payload["description"] == (
        "Notes: - 2m easy between sets\n\n- 1m intensity=warmup"
    )


@pytest.mark.parametrize(
    ("description", "text"),
    [
        (
            "- keep cadence high\n- 5m easy after",
            r"\- keep cadence high - 5m easy after",
        ),
        ("1. warm up well", r"1\. warm up well"),
        ("2) cool down", r"2\) cool down"),
        ("3.5h endurance", "3.5h endurance"),
        ("105-115% FTP", "105-115% FTP"),
    ],
)
def test_plan_description_never_starts_a_step_list(description, text):
    result = _payload(
        [{"type": "warmup", "duration_seconds": 60}], description=description
    )
    assert result.payload["description"] == f"{text}\n\n- 1m intensity=warmup"


@pytest.mark.parametrize(
    ("description", "text"),
    [
        ("Power: hold 105-115% FTP", r"Power\: hold 105-115% FTP"),
        ("category : VO2max", r"category \: VO2max"),
        ("Pool length: 25m", r"Pool length\: 25m"),
        ("Power zones: 1-7", "Power zones: 1-7"),
    ],
)
def test_plan_description_is_not_read_as_a_workout_option(description, text):
    result = _payload(
        [{"type": "warmup", "duration_seconds": 60}], description=description
    )
    assert result.payload["description"] == f"{text}\n\n- 1m intensity=warmup"


def test_repeats_are_separated_from_neighbouring_steps():
    effort = {"type": "interval", "duration_seconds": 30}
    result = _payload(
        [
            {"type": "repeat", "count": 2, "steps": [effort]},
            {"type": "repeat", "count": 4, "steps": [effort]},
            {"type": "cooldown", "duration_seconds": 60},
        ]
    )
    assert result.payload["description"] == (
        "2x\n- 30s intensity=interval\n\n"
        "4x\n- 30s intensity=interval\n\n"
        "- 1m intensity=cooldown"
    )


def test_nested_repeat_is_unrolled():
    effort = WorkoutStep(type="interval", duration_seconds=30, targets=())
    plan = WorkoutPlan(
        name="T",
        sport="cycling",
        steps=(RepeatStep(count=2, steps=(RepeatStep(count=2, steps=(effort,)),)),),
    )
    description = IntervalsWorkoutAdapter().to_payload(plan).payload["description"]
    assert description == "2x\n" + "\n".join(["- 30s intensity=interval"] * 2)


@pytest.mark.parametrize(("sport", "kind"), [("running", "Run"), ("swimming", "Swim")])
def test_sport_type(sport, kind):
    plan = parse_workout(
        {
            "name": "T",
            "sport": sport,
            "steps": [{"type": "warmup", "duration_seconds": 60}],
        }
    )
    assert IntervalsWorkoutAdapter().to_payload(plan).payload["type"] == kind


def test_every_supported_sport_and_target_type_is_mapped():
    assert set(_SPORT_TYPE) == SUPPORTED_SPORTS
    # Heart rate has no absolute form in the workout text, so it goes to the cue.
    assert SUPPORTED_TARGET_TYPES - set(_UNITS) == {"heart_rate"}
