from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

import pytest

from app.credentials.base import (
    CredentialRequest,
    CredentialsNotFoundError,
    InvalidMasterPasswordError,
)
from app.credentials.keepass import KeePassProvider, KeePassProviderFactory


def _req(service="garmin", url="garmin.com", login=None):
    return CredentialRequest(service=service, url=url, login=login)


def _mock_entry(username="user@test.com", url="https://garmin.com", password=None):
    entry = MagicMock()
    entry.username = username
    entry.password = password or "s3cr3t"
    entry.url = url
    return entry


def _mock_kp(entries=None):
    kp = MagicMock()
    kp.find_entries.return_value = entries or []
    return kp


def test_found_credentials():
    entry = _mock_entry()
    kp = _mock_kp([entry])
    with patch("app.credentials.keepass.PyKeePass", return_value=kp, create=True):
        creds = KeePassProvider("/fake/path.kdbx", "master").get(_req())
    assert creds.login == "user@test.com"
    assert creds.password == "s3cr3t"


def test_not_found_raises():
    kp = _mock_kp([])
    with patch("app.credentials.keepass.PyKeePass", return_value=kp, create=True):
        with pytest.raises(CredentialsNotFoundError):
            KeePassProvider("/fake/path.kdbx", "master").get(_req())


def test_bad_password_raises():
    from pykeepass.exceptions import CredentialsError

    with patch("app.credentials.keepass.PyKeePass", side_effect=CredentialsError()):
        with pytest.raises(InvalidMasterPasswordError):
            KeePassProvider("/fake/path.kdbx", "wrong").get(_req())


def test_factory_provider_name():
    assert KeePassProviderFactory().provider_name == "keepass"


def test_factory_add_cli_args_registers_flags():
    factory = KeePassProviderFactory()
    parser = argparse.ArgumentParser()
    factory.add_cli_args(parser)
    args = parser.parse_args(
        ["--creds-keepass", "/path/to.kdbx", "--keepass-password", "pass"]
    )
    assert args.creds_keepass == "/path/to.kdbx"
    assert args.keepass_password == "pass"


def test_factory_build_missing_path_raises():
    factory = KeePassProviderFactory()
    parser = argparse.ArgumentParser()
    factory.add_cli_args(parser)
    args = parser.parse_args([])
    with pytest.raises(ValueError, match="--creds-keepass"):
        factory.build_from_args(args)


def test_factory_build_from_args_uses_env_password(tmp_path, monkeypatch):
    monkeypatch.setenv("KEEPASS_PASSWORD", "env_pass")
    kdbx = tmp_path / "db.kdbx"
    kdbx.touch()
    entry = _mock_entry()
    kp = _mock_kp([entry])

    factory = KeePassProviderFactory()
    parser = argparse.ArgumentParser()
    factory.add_cli_args(parser)
    args = parser.parse_args(["--creds-keepass", str(kdbx)])

    with patch("app.credentials.keepass.PyKeePass", return_value=kp) as mock_kp:
        provider = factory.build_from_args(args)
        provider.get(_req())
        mock_kp.assert_called_once_with(str(kdbx), password="env_pass")


def test_login_filter_matches_correctly():
    entry_a = _mock_entry(username="a@test.com", password="pa")
    entry_b = _mock_entry(username="b@test.com", password="pb")
    kp = _mock_kp([entry_a, entry_b])
    with patch("app.credentials.keepass.PyKeePass", return_value=kp, create=True):
        creds = KeePassProvider("/fake/path.kdbx", "master").get(
            _req(login="b@test.com")
        )
    assert creds.login == "b@test.com"
    assert creds.password == "pb"
