"""The FIT file is read back here with an independent decoder and CRC."""

import base64
import json
import struct
from pathlib import Path

from app.adapters.fit_workout import FitWorkoutAdapter
from app.models.parser import parse_workout
from app.models.workout import SUPPORTED_SPORTS, SUPPORTED_STEP_TYPES

_EXAMPLE = Path(__file__).parents[2] / "examples" / "cycling_intervals.json"
_NOW = 1_763_000_000  # a fixed Unix time, so time_created is known
_E_ACUTE = chr(0xE9)  # a two-byte letter in UTF-8


def _crc16_arc(data: bytes) -> int:
    """CRC-16/ARC, bit by bit; FIT files use this CRC."""
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def _read_fit(data: bytes) -> list[tuple[int, dict[int, int | str]]]:
    header_size, protocol, _profile, data_size, magic = struct.unpack_from(
        "<BBHI4s", data
    )
    assert (header_size, protocol, magic) == (14, 0x10, b".FIT")
    assert len(data) == header_size + data_size + 2
    assert struct.unpack_from("<H", data, 12)[0] == _crc16_arc(data[:12])
    assert struct.unpack_from("<H", data, len(data) - 2)[0] == _crc16_arc(data[:-2])

    definitions: dict[int, tuple[int, list[bytes]]] = {}
    messages: list[tuple[int, dict[int, int | str]]] = []
    pos, end = header_size, header_size + data_size
    while pos < end:
        record_header = data[pos]
        pos += 1
        local = record_header & 0x0F
        if record_header & 0x40:
            _reserved, architecture, number, count = struct.unpack_from(
                "<BBHB", data, pos
            )
            assert architecture == 0  # little endian
            pos += 5
            fields = [data[pos + 3 * i : pos + 3 * i + 3] for i in range(count)]
            pos += 3 * count
            definitions[local] = (number, fields)
            continue
        number, fields = definitions[local]
        values: dict[int, int | str] = {}
        for field_number, size, base_type in fields:
            raw = data[pos : pos + size]
            pos += size
            if base_type == 0x07:
                assert raw.endswith(b"\x00")
                values[field_number] = raw[:-1].decode()
            else:
                values[field_number] = int.from_bytes(raw, "little")
        messages.append((number, values))
    return messages


def _decoded(plan_data: dict, monkeypatch) -> tuple[list, list[str]]:
    monkeypatch.setattr("app.adapters.fit_workout.time.time", lambda: _NOW + 0.7)
    result = FitWorkoutAdapter().to_payload(parse_workout(plan_data))
    data = base64.b64decode(result.payload["content_base64"])
    return _read_fit(data), result.warnings


def test_connector_name():
    assert FitWorkoutAdapter().connector_name == "fit-file"


def test_example_plan_becomes_a_fit_workout(monkeypatch):
    messages, warnings = _decoded(json.loads(_EXAMPLE.read_text()), monkeypatch)

    assert messages[0] == (0, {0: 5, 1: 255, 2: 0, 4: _NOW - 631065600})
    assert messages[1] == (26, {4: 2, 6: 6, 8: "3x8 Cycling Intervals"})
    steps = [values for number, values in messages[2:]]
    assert all(number == 27 for number, _ in messages[2:])
    assert steps == [
        # Easy Spin: 10 min at 130-170 W (watts are stored as watts + 1000).
        {254: 0, 0: "Easy Spin", 1: 0, 2: 600_000, 3: 4, 4: 0, 5: 1130, 6: 1170, 7: 2},
        # 1km Build: the distance is in centimetres.
        {254: 1, 0: "1km Build", 1: 1, 2: 100_000, 3: 4, 4: 0, 5: 1200, 6: 1240, 7: 5},
        # 8min Effort: power first, heart rate second (bpm + 100), cadence dropped.
        {
            254: 2,
            0: "8min Effort",
            1: 0,
            2: 480_000,
            3: 4,
            4: 0,
            5: 1260,
            6: 1300,
            19: 1,
            20: 0,
            21: 255,
            22: 265,
            7: 5,
        },
        # Active Recovery: an open step that ends on the lap button.
        {254: 3, 0: "Active Recovery", 1: 5, 3: 1, 4: 0, 5: 210, 6: 230, 7: 1},
        # The repeat sends the device back to step 2, three times in all.
        {254: 4, 1: 6, 2: 2, 3: 2, 4: 3},
        {
            254: 5,
            0: "Easy Spin Down",
            1: 0,
            2: 300_000,
            3: 4,
            4: 0,
            5: 1090,
            6: 1120,
            7: 3,
        },
    ]
    assert warnings == [
        "Step 'interval': FIT steps take 2 targets; cadence dropped "
        "(power, heart_rate kept)"
    ]


def test_cadence_and_a_step_without_targets(monkeypatch):
    cadence = {"type": "cadence", "low": 85, "high": 95}
    messages, warnings = _decoded(
        {
            "name": "Run",
            "sport": "running",
            "steps": [
                {"type": "interval", "duration_seconds": 60, "targets": [cadence]},
                {"type": "rest", "duration_seconds": 30},
            ],
        },
        monkeypatch,
    )
    assert messages[1] == (26, {4: 1, 6: 2, 8: "Run"})
    assert messages[2][1] == {254: 0, 1: 0, 2: 60_000, 3: 3, 4: 0, 5: 85, 6: 95, 7: 5}
    assert messages[3][1] == {254: 1, 1: 0, 2: 30_000, 3: 2, 7: 1}
    assert warnings == []


def test_swim_workouts_are_pool_swims(monkeypatch):
    messages, _ = _decoded(
        {
            "name": "Swim",
            "sport": "swimming",
            "steps": [
                {
                    "type": "interval",
                    "duration_type": "distance",
                    "duration_seconds": 100,
                }
            ],
        },
        monkeypatch,
    )
    assert messages[1] == (26, {4: 5, 6: 1, 8: "Swim", 11: 17})


def test_long_names_are_cut_to_the_field_size(monkeypatch):
    messages, _ = _decoded(
        {
            "name": _E_ACUTE * 200,
            "sport": "cycling",
            "steps": [{"type": "rest", "duration_seconds": 1}],
        },
        monkeypatch,
    )
    # 127 two-byte letters fit in 254 bytes; half a letter is never written.
    assert messages[1][1][8] == _E_ACUTE * 127


def test_every_sport_and_step_type_is_mapped():
    from app.adapters.fit_workout import _INTENSITY, _SPORT

    assert set(_SPORT) == SUPPORTED_SPORTS
    assert set(_INTENSITY) == SUPPORTED_STEP_TYPES


def test_reference_crc():
    # The standard check value of CRC-16/ARC proves the reference decoder.
    assert _crc16_arc(b"123456789") == 0xBB3D
