from app.cache import WorkoutCache


def test_save_connector_payload_writes_json(tmp_path):
    cache = WorkoutCache(tmp_path)
    payload = {"workoutName": "Test", "steps": []}
    path = cache.save_connector_payload("My Workout", "garmin", payload)
    assert path == tmp_path / "workouts" / "my_workout.garmin.json"
    assert '"workoutName"' in path.read_text()


def test_save_source_plan_writes_bytes(tmp_path):
    cache = WorkoutCache(tmp_path)
    data = b'{"name": "test"}'
    path = cache.save_source_plan("Test Plan", data)
    assert path == tmp_path / "workouts" / "test_plan.source.json"
    assert path.read_bytes() == data


def test_overwrite_by_slug(tmp_path):
    cache = WorkoutCache(tmp_path)
    payload = {"workoutName": "Test"}
    cache.save_connector_payload("Test", "garmin", payload)
    path = cache.save_connector_payload("Test", "garmin", {"workoutName": "Updated"})
    assert "Updated" in path.read_text()


def test_workouts_dir_created_on_first_save(tmp_path):
    cache = WorkoutCache(tmp_path)
    assert not (tmp_path / "workouts").exists()
    cache.save_source_plan("Test", b"{}")
    assert (tmp_path / "workouts").exists()


def test_list_workouts_returns_sorted_paths(tmp_path):
    cache = WorkoutCache(tmp_path)
    cache.save_connector_payload("B Workout", "garmin", {})
    cache.save_connector_payload("A Workout", "garmin", {})
    paths = cache.list_workouts()
    names = [p.name for p in paths]
    assert names == sorted(names)


def test_list_workouts_empty_when_no_files(tmp_path):
    cache = WorkoutCache(tmp_path)
    assert cache.list_workouts() == []


def test_slugify_special_chars(tmp_path):
    cache = WorkoutCache(tmp_path)
    path = cache.save_source_plan("Test: Workout! #1", b"{}")
    assert " " not in path.name
    assert "!" not in path.name
