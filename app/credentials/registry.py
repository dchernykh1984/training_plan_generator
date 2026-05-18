from __future__ import annotations

from app.credentials.base import CredentialProviderFactory
from app.credentials.json_file import JsonFileProviderFactory
from app.credentials.keepass import KeePassProviderFactory

PROVIDER_FACTORIES: dict[str, CredentialProviderFactory] = {
    "json": JsonFileProviderFactory(),
    "keepass": KeePassProviderFactory(),
}


def get_factory(provider_name: str) -> CredentialProviderFactory:
    factory = PROVIDER_FACTORIES.get(provider_name)
    if factory is None:
        supported = sorted(PROVIDER_FACTORIES)
        raise ValueError(
            f"Unknown credentials provider: {provider_name!r}. Supported: {supported}"
        )
    return factory
