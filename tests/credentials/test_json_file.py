import json
import warnings

import pytest

from app.credentials.base import CredentialRequest, CredentialsNotFoundError
from app.credentials.json_file import JsonFileProvider, JsonFileProviderFactory


def _write_creds(tmp_path, entries):
    p = tmp_path / "creds.json"
    p.write_text(json.dumps(entries))
    return p


def _entry(service="garmin", url="https://garmin.com", login="u@test.com", pw="pw"):
    return {"service": service, "url": url, "login": login, "password": pw}


def _req(service="garmin", url="garmin.com", login=None):
    return CredentialRequest(service=service, url=url, login=login)


def test_found_credentials(tmp_path):
    path = _write_creds(tmp_path, [_entry(login="user@test.com", pw="s3cr3t")])
    creds = JsonFileProvider(path).get(_req())
    assert creds.login == "user@test.com"
    assert creds.password == "s3cr3t"


def test_not_found_raises(tmp_path):
    path = _write_creds(tmp_path, [_entry(service="strava", url="https://strava.com")])
    with pytest.raises(CredentialsNotFoundError):
        JsonFileProvider(path).get(_req())


def test_login_filter(tmp_path):
    path = _write_creds(
        tmp_path,
        [_entry(login="a@test.com", pw="pa"), _entry(login="b@test.com", pw="pb")],
    )
    creds = JsonFileProvider(path).get(_req(login="b@test.com"))
    assert creds.login == "b@test.com"
    assert creds.password == "pb"


def test_multiple_matches_warns_uses_first(tmp_path):
    path = _write_creds(
        tmp_path,
        [_entry(login="a@test.com", pw="pa"), _entry(login="b@test.com", pw="pb")],
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        creds = JsonFileProvider(path).get(_req())
    assert any("Multiple" in str(w.message) for w in caught)
    assert creds.login == "a@test.com"


def test_malformed_file_raises(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("not valid json {{{")
    with pytest.raises(json.JSONDecodeError):
        JsonFileProvider(path).get(_req())


def test_factory_provider_name():
    assert JsonFileProviderFactory().provider_name == "json"


def test_factory_build_from_args(tmp_path):
    import argparse

    path = _write_creds(tmp_path, [_entry(login="u", pw="p")])
    factory = JsonFileProviderFactory()
    parser = argparse.ArgumentParser()
    factory.add_cli_args(parser)
    args = parser.parse_args(["--creds-json", str(path)])
    provider = factory.build_from_args(args)
    creds = provider.get(_req())
    assert creds.login == "u"


def test_factory_build_from_args_missing_path_raises():
    import argparse

    factory = JsonFileProviderFactory()
    parser = argparse.ArgumentParser()
    factory.add_cli_args(parser)
    args = parser.parse_args([])
    with pytest.raises(ValueError, match="--creds-json"):
        factory.build_from_args(args)
