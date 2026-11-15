import json
from pathlib import Path

import pytest

from app.adapters.erg_workout import ErgWorkoutAdapter
from app.models.parser import parse_workout

_EXAMPLE = Path(__file__).parents[2] / "examples" / "cycling_intervals.json"

_EXAMPLE_ERG = """\
[COURSE HEADER]
VERSION = 2
UNITS = ENGLISH
DESCRIPTION = VO2max build block: 3 sets of 8-minute efforts at 105-115% FTP
FILE NAME = 3x8 Cycling Intervals
MINUTES WATTS
[END COURSE HEADER]
[COURSE DATA]
0.00\t150
10.00\t150
10.00\t220
15.00\t220
15.00\t280
23.00\t280
23.00\t0
28.00\t0
28.00\t280
36.00\t280
36.00\t0
41.00\t0
41.00\t280
49.00\t280
49.00\t0
54.00\t0
54.00\t105
59.00\t105
[END COURSE DATA]
"""


def _payload(steps, **plan_fields):
    plan = parse_workout(
        {"name": "T", "sport": "cycling", "steps": steps, **plan_fields}
    )
    return ErgWorkoutAdapter().to_payload(plan)


def test_connector_name():
    assert ErgWorkoutAdapter().connector_name == "erg-file"


def test_example_plan_becomes_an_erg_course():
    plan = parse_workout(json.loads(_EXAMPLE.read_text()))
    result = ErgWorkoutAdapter().to_payload(plan)

    assert result.payload == {"name": "3x8 Cycling Intervals", "content": _EXAMPLE_ERG}
    assert result.warnings == [
        "ERG files hold one power per step; each power range is set to its middle",
        "ERG files hold only power; step names, cadence and heart rate are left out",
        "Step 'interval': ERG steps are timed; 1000 m step planned as 5m",
        "Step 'rest': ERG steps are timed; open step planned as 5m",
        "Step 'rest': ERG files need power; a step without a power target is set "
        "to 0 W",
    ]


def test_power_only_plan_needs_no_warnings():
    power = {"type": "power", "low": 200, "high": 200}
    result = _payload(
        [{"type": "interval", "duration_seconds": 90, "targets": [power]}],
        description="Line one\nline two",
    )
    assert result.warnings == []
    content = result.payload["content"]
    assert "DESCRIPTION = Line one line two\n" in content
    assert "0.00\t200\n1.50\t200\n" in content


@pytest.mark.parametrize("sport", ["running", "swimming"])
def test_only_rides_become_erg_files(sport):
    plan = parse_workout(
        {
            "name": "T",
            "sport": sport,
            "steps": [{"type": "rest", "duration_seconds": 1}],
        }
    )
    with pytest.raises(ValueError, match="ERG files are rides"):
        ErgWorkoutAdapter().to_payload(plan)
