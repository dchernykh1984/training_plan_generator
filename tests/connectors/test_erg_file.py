import pytest

from app.connectors.erg_file import ErgFileConnector


def test_connector_name_and_extension():
    assert ErgFileConnector().connector_name == "erg-file"
    assert ErgFileConnector.extension == ".erg"


def test_needs_a_chosen_folder():
    assert not ErgFileConnector.has_default_folder
    with pytest.raises(RuntimeError, match=r"Choose the folder to write \.erg files"):
        ErgFileConnector().login()
