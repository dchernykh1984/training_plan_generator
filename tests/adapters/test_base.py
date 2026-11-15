import pytest

from app.adapters.base import MAX_FLAT_STEPS, flatten_steps
from app.models.workout import RepeatStep, WorkoutStep

_STEP = WorkoutStep(type="interval", duration_seconds=30, targets=())


def test_repeats_are_written_out_in_order():
    rest = WorkoutStep(type="rest", duration_seconds=10, targets=())
    steps = (RepeatStep(count=2, steps=(_STEP, rest)),)
    assert flatten_steps(steps) == [_STEP, rest, _STEP, rest]


def test_a_huge_repeat_is_refused_before_it_is_built():
    steps = (RepeatStep(count=10**9, steps=(_STEP, _STEP)),)
    with pytest.raises(ValueError, match="2000000000 steps once repeats are written"):
        flatten_steps(steps)


def test_the_limit_itself_is_allowed():
    steps = (RepeatStep(count=MAX_FLAT_STEPS, steps=(_STEP,)),)
    assert len(flatten_steps(steps)) == MAX_FLAT_STEPS
