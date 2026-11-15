import pytest

from app.connectors import zwift
from app.connectors.zwift import ZwiftConnector


@pytest.fixture
def workouts_root(tmp_path, monkeypatch):
    monkeypatch.setattr(zwift, "_WORKOUTS_ROOT", tmp_path)
    return tmp_path


def test_finds_the_only_zwift_account_folder(workouts_root):
    (workouts_root / "123456").mkdir()
    (workouts_root / "notes").mkdir()
    connector = ZwiftConnector()
    connector.login()
    assert connector.folder == workouts_root / "123456"


def test_explains_a_missing_zwift_folder(workouts_root):
    with pytest.raises(RuntimeError, match="start Zwift once"):
        ZwiftConnector().login()


def test_asks_to_choose_between_several_accounts(workouts_root):
    (workouts_root / "111").mkdir()
    (workouts_root / "222").mkdir()
    with pytest.raises(RuntimeError, match=r"Several Zwift accounts .*\(111, 222\)"):
        ZwiftConnector().login()


def test_a_chosen_folder_wins(workouts_root, tmp_path):
    (workouts_root / "111").mkdir()
    chosen = tmp_path / "elsewhere"
    chosen.mkdir()
    connector = ZwiftConnector(chosen)
    connector.login()
    assert connector.folder == chosen


def test_connector_name_and_extension():
    assert ZwiftConnector().connector_name == "zwift"
    assert ZwiftConnector.extension == ".zwo"
