from __future__ import annotations

import argparse
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class CredentialRequest:
    service: str
    url: str
    login: str | None = None


@dataclass(frozen=True)
class Credentials:
    login: str
    password: str


class CredentialsNotFoundError(Exception):
    pass


class InvalidMasterPasswordError(Exception):
    pass


class CredentialProvider(ABC):
    @abstractmethod
    def get(self, request: CredentialRequest) -> Credentials: ...


class CredentialProviderFactory(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @abstractmethod
    def add_cli_args(self, parser: argparse.ArgumentParser) -> None: ...

    @abstractmethod
    def build_from_args(self, args: argparse.Namespace) -> CredentialProvider: ...
