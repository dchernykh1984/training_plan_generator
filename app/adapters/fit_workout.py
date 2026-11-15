"""WorkoutPlan -> FIT workout file, the format Garmin and most bike computers load.

Only the three messages a workout file needs are written: ``file_id``,
``workout`` and one ``workout_step`` per step, each after its own definition.
Field numbers and enum values come from the FIT profile.
"""

from __future__ import annotations

import base64
import struct
import time

from app.adapters.base import AdapterResult, PayloadAdapter
from app.models.workout import RepeatStep, Target, WorkoutPlan, WorkoutStep

# (FIT base type number, struct format) by the name used below.
_BASE_TYPES = {"enum": (0x00, "B"), "uint16": (0x84, "H"), "uint32": (0x86, "I")}
_STRING = 0x07
_MAX_STRING_BYTES = 254  # a field holds at most 255 bytes with the trailing NUL

_FILE_ID, _WORKOUT, _WORKOUT_STEP = 0, 26, 27
_FILE_TYPE_WORKOUT = 5
_MANUFACTURER_DEVELOPMENT = 255
_SPORT = {"running": 1, "cycling": 2, "swimming": 5}
_SUB_SPORT_LAP_SWIMMING = 17
_INTENSITY = {"warmup": 2, "cooldown": 3, "interval": 5, "rest": 1}
_DURATION_TIME, _DURATION_DISTANCE, _DURATION_OPEN, _DURATION_REPEAT = 0, 1, 5, 6
_TARGET = {"power": 4, "heart_rate": 1, "cadence": 3}
_TARGET_OPEN = 2
# Custom targets above these offsets are absolute: watts + 1000, bpm + 100.
_TARGET_OFFSET = {"power": 1000, "heart_rate": 100, "cadence": 0}
# A step has a primary and a secondary target; this order picks them.
_PRIORITY = ("power", "heart_rate", "cadence")
_FIT_EPOCH = 631065600  # 1989-12-31T00:00:00Z, where FIT time starts

_CRC_TABLE = (
    0x0000,
    0xCC01,
    0xD801,
    0x1400,
    0xF001,
    0x3C00,
    0x2800,
    0xE401,
    0xA001,
    0x6C00,
    0x7800,
    0xB401,
    0x5000,
    0x9C01,
    0x8801,
    0x4400,
)

Field = tuple[int, str, int | str]


def _crc(data: bytes) -> int:
    crc = 0
    for byte in data:
        for nibble in (byte & 0x0F, byte >> 4):
            tmp = _CRC_TABLE[crc & 0x0F]
            crc = (crc >> 4) & 0x0FFF
            crc ^= tmp ^ _CRC_TABLE[nibble]
    return crc


def _message(global_number: int, fields: list[Field]) -> bytes:
    """A definition record and a data record, both as local message type 0."""
    definition = bytearray(
        struct.pack("<BBBHB", 0x40, 0, 0, global_number, len(fields))
    )
    data = bytearray(b"\x00")
    for number, kind, value in fields:
        if kind == "string":
            text = str(value).encode()[:_MAX_STRING_BYTES]
            raw = text.decode(errors="ignore").encode() + b"\x00"
            definition += bytes([number, len(raw), _STRING])
        else:
            base_type, fmt = _BASE_TYPES[kind]
            raw = struct.pack("<" + fmt, value)
            definition += bytes([number, len(raw), base_type])
        data += raw
    return bytes(definition + data)


def _target_fields(
    targets: list[Target], type_field: int, value_fields: tuple[int, int, int]
) -> list[Field]:
    if not targets:
        return [(type_field, "enum", _TARGET_OPEN)]
    target = targets[0]
    offset = _TARGET_OFFSET[target.type]
    value, low, high = value_fields
    return [
        (type_field, "enum", _TARGET[target.type]),
        (value, "uint32", 0),
        (low, "uint32", int(target.low) + offset),
        (high, "uint32", int(target.high) + offset),
    ]


def _step_fields(step: WorkoutStep, index: int, warnings: list[str]) -> list[Field]:
    fields: list[Field] = [(254, "uint16", index)]
    if step.name:
        fields.append((0, "string", " ".join(step.name.split())))
    if step.duration_seconds is None:
        fields.append((1, "enum", _DURATION_OPEN))
    elif step.duration_type == "distance":
        fields += [
            (1, "enum", _DURATION_DISTANCE),
            (2, "uint32", step.duration_seconds * 100),
        ]
    else:
        fields += [
            (1, "enum", _DURATION_TIME),
            (2, "uint32", step.duration_seconds * 1000),
        ]

    targets = sorted(step.targets, key=lambda t: _PRIORITY.index(t.type))
    if len(targets) > 2:
        kept = ", ".join(t.type for t in targets[:2])
        warnings.append(
            f"Step '{step.type}': FIT steps take 2 targets; {targets[2].type} "
            f"dropped ({kept} kept)"
        )
    fields += _target_fields(targets[:1], 3, (4, 5, 6))
    if len(targets) > 1:
        fields += _target_fields(targets[1:2], 19, (20, 21, 22))
    fields.append((7, "enum", _INTENSITY[step.type]))
    return fields


def _steps(
    steps: tuple[WorkoutStep | RepeatStep, ...], warnings: list[str]
) -> list[list[Field]]:
    records: list[list[Field]] = []

    def add(sequence: tuple[WorkoutStep | RepeatStep, ...]) -> None:
        for step in sequence:
            if isinstance(step, RepeatStep):
                first = len(records)
                add(step.steps)
                # A repeat step sends the device back to the first step it repeats.
                records.append(
                    [
                        (254, "uint16", len(records)),
                        (1, "enum", _DURATION_REPEAT),
                        (2, "uint32", first),
                        (3, "enum", _TARGET_OPEN),
                        (4, "uint32", step.count),
                    ]
                )
            else:
                records.append(_step_fields(step, len(records), warnings))

    add(steps)
    return records


class FitWorkoutAdapter(PayloadAdapter):
    @property
    def connector_name(self) -> str:
        return "fit-file"

    def to_payload(self, plan: WorkoutPlan) -> AdapterResult:
        warnings: list[str] = []
        steps = _steps(plan.steps, warnings)
        workout: list[Field] = [
            (4, "enum", _SPORT[plan.sport]),
            (6, "uint16", len(steps)),
            (8, "string", " ".join(plan.name.split())),
        ]
        if plan.sport == "swimming":
            workout.append((11, "enum", _SUB_SPORT_LAP_SWIMMING))
        records = _message(
            _FILE_ID,
            [
                (0, "enum", _FILE_TYPE_WORKOUT),
                (1, "uint16", _MANUFACTURER_DEVELOPMENT),
                (2, "uint16", 0),
                (4, "uint32", int(time.time()) - _FIT_EPOCH),
            ],
        )
        records += _message(_WORKOUT, workout)
        for step in steps:
            records += _message(_WORKOUT_STEP, step)
        # Protocol 1.0 is the one every device reads; nothing here needs 2.0.
        header = struct.pack("<BBHI4s", 14, 0x10, 2100, len(records), b".FIT")
        header += struct.pack("<H", _crc(header))
        data = header + records
        data += struct.pack("<H", _crc(data))
        payload = {"name": plan.name, "content_base64": base64.b64encode(data).decode()}
        return AdapterResult(payload, warnings)
