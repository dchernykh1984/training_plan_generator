import json
from pathlib import Path

import pytest

from app.adapters.zwift_workout import ZwiftWorkoutAdapter
from app.models.parser import parse_workout
from app.models.workout import (
    SUPPORTED_TARGET_TYPES,
    RepeatStep,
    WorkoutPlan,
    WorkoutStep,
)

_EXAMPLE = Path(__file__).parents[2] / "examples" / "cycling_intervals.json"

_EFFORT = """\
    <SteadyState Duration="480" Power="1.077" Cadence="90">
      <textevent timeoffset="0" message="8min Effort - HR 155-165 bpm" />
    </SteadyState>
    <FreeRide Duration="300">
      <textevent timeoffset="0" message="Active Recovery - HR 110-130 bpm" />
    </FreeRide>
"""

_EXAMPLE_ZWO = (
    """\
<workout_file>
  <author>Training Plan Generator</author>
  <name>3x8 Cycling Intervals</name>
  <description>VO2max build block: 3 sets of 8-minute efforts at 105-115% FTP\
</description>
  <sportType>bike</sportType>
  <workout>
    <Warmup Duration="600" PowerLow="0.577" PowerHigh="0.577">
      <textevent timeoffset="0" message="Easy Spin" />
    </Warmup>
    <SteadyState Duration="300" Power="0.846">
      <textevent timeoffset="0" message="1km Build" />
    </SteadyState>
"""
    + _EFFORT * 3
    + """\
    <Cooldown Duration="300" PowerLow="0.404" PowerHigh="0.404">
      <textevent timeoffset="0" message="Easy Spin Down" />
    </Cooldown>
  </workout>
</workout_file>
"""
)


def _content(steps, **plan_fields):
    plan = parse_workout(
        {"name": "T", "sport": "cycling", "steps": steps, **plan_fields}
    )
    result = ZwiftWorkoutAdapter().to_payload(plan)
    return result.payload["content"], result.warnings


def test_connector_name():
    assert ZwiftWorkoutAdapter().connector_name == "zwift"


def test_example_plan_becomes_a_zwift_workout():
    plan = parse_workout(json.loads(_EXAMPLE.read_text()))
    result = ZwiftWorkoutAdapter().to_payload(plan)

    assert result.payload == {"name": "3x8 Cycling Intervals", "content": _EXAMPLE_ZWO}
    # Each warning shows once although the repeat has three laps.
    assert result.warnings == [
        "Zwift holds one power per step; each power range is set to its middle",
        "Step 'interval': Zwift steps are timed; 1000 m step planned as 5m",
        "Step 'interval': Zwift has no heart rate targets; 155-165 bpm kept in "
        "the step text",
        "Step 'rest': Zwift steps are timed; open step planned as 5m",
        "Step 'rest': Zwift has no heart rate targets; 110-130 bpm kept in "
        "the step text",
    ]


def test_power_without_ftp_becomes_a_free_ride_with_a_warning():
    power = {"type": "power", "low": 200, "high": 200}
    content, warnings = _content(
        [{"type": "interval", "duration_seconds": 60, "targets": [power]}]
    )
    assert '<FreeRide Duration="60" />' in content
    assert warnings == [
        "Zwift sets power as a share of FTP; add ftp_watts to the plan to keep "
        "its power targets"
    ]


def test_a_single_power_value_needs_no_range_warning():
    power = {"type": "power", "low": 250, "high": 250}
    content, warnings = _content(
        [{"type": "interval", "duration_seconds": 60, "targets": [power]}],
        ftp_watts=250,
    )
    assert '<SteadyState Duration="60" Power="1.0" />' in content
    assert warnings == []


def test_names_are_escaped_and_collapsed():
    plan = WorkoutPlan(
        name='A <b> & "c"',
        sport="cycling",
        steps=(
            WorkoutStep(type="rest", duration_seconds=60, targets=(), name='x\n "y"'),
        ),
    )
    content = ZwiftWorkoutAdapter().to_payload(plan).payload["content"]
    assert '<name>A &lt;b&gt; &amp; "c"</name>' in content
    assert 'message="x &quot;y&quot;"' in content


def test_a_nested_repeat_is_unrolled():
    effort = WorkoutStep(type="interval", duration_seconds=30, targets=())
    plan = WorkoutPlan(
        name="T",
        sport="cycling",
        steps=(RepeatStep(count=2, steps=(RepeatStep(count=3, steps=(effort,)),)),),
    )
    content = ZwiftWorkoutAdapter().to_payload(plan).payload["content"]
    assert content.count('<FreeRide Duration="30" />') == 6


@pytest.mark.parametrize("sport", ["running", "swimming"])
def test_only_rides_are_zwift_workouts(sport):
    plan = parse_workout(
        {
            "name": "T",
            "sport": sport,
            "steps": [{"type": "rest", "duration_seconds": 1}],
        }
    )
    with pytest.raises(ValueError, match="Zwift workouts are rides"):
        ZwiftWorkoutAdapter().to_payload(plan)


def test_every_target_type_is_handled():
    # Power and cadence become attributes and heart rate goes to the text, so a
    # new target type needs a decision here before it reaches Zwift.
    assert SUPPORTED_TARGET_TYPES == {"power", "cadence", "heart_rate"}
