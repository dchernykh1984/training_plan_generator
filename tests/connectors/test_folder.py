import base64
import datetime

import pytest

from app.connectors.folder import FolderConnector


class _TextConnector(FolderConnector):
    extension = ".txt"

    @property
    def connector_name(self) -> str:
        return "text"


def test_login_checks_the_folder(tmp_path):
    with pytest.raises(RuntimeError, match="Folder not found"):
        _TextConnector(tmp_path / "missing").login()


def test_a_folder_is_required_without_a_default():
    with pytest.raises(RuntimeError, match=r"Choose the folder to write \.txt files"):
        _TextConnector().login()


def test_upload_writes_the_text_under_the_workout_name(tmp_path):
    connector = _TextConnector(tmp_path)
    connector.login()

    path = connector.upload({"name": "Z2 / Easy!", "content": "hello"})

    assert path == str(tmp_path / "z2_easy.txt")
    assert (tmp_path / "z2_easy.txt").read_text() == "hello"


def test_a_dated_upload_starts_the_file_name_with_the_day(tmp_path):
    connector = _TextConnector(tmp_path)
    connector.login()

    connector.upload({"name": "Z2", "content": "x"}, datetime.date(2026, 11, 20))

    assert (tmp_path / "2026-11-20_z2.txt").exists()


def test_upload_writes_binary_content(tmp_path):
    connector = _TextConnector(tmp_path)
    connector.login()
    data = bytes([0, 1, 254, 255])

    connector.upload({"name": "!!", "content_base64": base64.b64encode(data).decode()})

    # A name with no letters or digits still gets a usable file name.
    assert (tmp_path / "workout.txt").read_bytes() == data


def test_upload_without_login_raises(tmp_path):
    with pytest.raises(RuntimeError, match="call login"):
        _TextConnector(tmp_path).upload({"name": "W", "content": ""})
