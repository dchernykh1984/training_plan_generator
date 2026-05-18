import pytest

from app.credentials.base import (
    CredentialProvider,
    CredentialProviderFactory,
    CredentialRequest,
    Credentials,
)
from app.credentials.json_file import JsonFileProviderFactory
from app.credentials.keepass import KeePassProviderFactory
from app.credentials.registry import PROVIDER_FACTORIES, get_factory


def test_get_json_factory():
    factory = get_factory("json")
    assert isinstance(factory, JsonFileProviderFactory)


def test_get_keepass_factory():
    factory = get_factory("keepass")
    assert isinstance(factory, KeePassProviderFactory)


def test_get_unknown_raises():
    with pytest.raises(ValueError, match="Unknown credentials provider"):
        get_factory("vault")


def test_fake_provider_registered_and_retrieved():
    import argparse

    class FakeProvider(CredentialProvider):
        def get(self, request: CredentialRequest) -> Credentials:
            return Credentials(login="fake", password="fake")

    class FakeFactory(CredentialProviderFactory):
        @property
        def provider_name(self) -> str:
            return "fake"

        def add_cli_args(self, parser: argparse.ArgumentParser) -> None:
            pass

        def build_from_args(self, args: argparse.Namespace) -> CredentialProvider:
            return FakeProvider()

    PROVIDER_FACTORIES["fake"] = FakeFactory()
    try:
        factory = get_factory("fake")
        assert factory.provider_name == "fake"
        provider = factory.build_from_args(argparse.Namespace())
        creds = provider.get(CredentialRequest(service="x", url="x"))
        assert creds.login == "fake"
    finally:
        del PROVIDER_FACTORIES["fake"]


def test_registry_does_not_contain_fake_after_cleanup():
    assert "fake" not in PROVIDER_FACTORIES
