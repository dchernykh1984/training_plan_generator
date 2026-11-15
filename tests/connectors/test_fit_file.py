from app.connectors.fit_file import FitFileConnector


def test_connector_name_and_extension():
    assert FitFileConnector().connector_name == "fit-file"
    assert FitFileConnector.extension == ".fit"
    assert not FitFileConnector.has_default_folder
