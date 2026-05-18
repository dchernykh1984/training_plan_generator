from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path

from pykeepass import PyKeePass
from pykeepass.exceptions import CredentialsError

from app.credentials.base import (
    CredentialProvider,
    CredentialProviderFactory,
    CredentialRequest,
    Credentials,
    CredentialsNotFoundError,
    InvalidMasterPasswordError,
)


class KeePassProvider(CredentialProvider):
    def __init__(self, path: Path, password: str) -> None:
        self._path = path
        self._password = password

    def get(self, request: CredentialRequest) -> Credentials:
        try:
            kp = PyKeePass(str(self._path), password=self._password)
        except CredentialsError as e:
            raise InvalidMasterPasswordError("Invalid KeePass master password") from e

        entries = kp.find_entries(title=request.service, regex=False)
        matches = [
            e
            for e in (entries or [])
            if request.url in (e.url or "")
            and (request.login is None or e.username == request.login)
        ]
        if not matches:
            raise CredentialsNotFoundError(
                f"No KeePass entry found for service={request.service!r} "
                f"url={request.url!r}"
            )
        entry = matches[0]
        return Credentials(login=entry.username, password=entry.password)


class KeePassProviderFactory(CredentialProviderFactory):
    @property
    def provider_name(self) -> str:
        return "keepass"

    def add_cli_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--creds-keepass",
            metavar="PATH",
            help="Path to KeePass .kdbx file",
        )
        parser.add_argument(
            "--keepass-password",
            metavar="PASSWORD",
            help="KeePass master password (falls back to KEEPASS_PASSWORD env var)",
        )

    def build_from_args(self, args: argparse.Namespace) -> CredentialProvider:
        if not args.creds_keepass:
            raise ValueError("--creds-keepass PATH is required for keepass provider")
        password = (
            args.keepass_password
            or os.environ.get("KEEPASS_PASSWORD")
            or getpass.getpass("KeePass master password: ")
        )
        return KeePassProvider(Path(args.creds_keepass), password)
