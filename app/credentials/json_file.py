from __future__ import annotations

import argparse
import json
import logging
import warnings
from pathlib import Path

from app.credentials.base import (
    CredentialProvider,
    CredentialProviderFactory,
    CredentialRequest,
    Credentials,
    CredentialsNotFoundError,
)

logger = logging.getLogger(__name__)


class JsonFileProvider(CredentialProvider):
    def __init__(self, path: Path) -> None:
        self._path = path

    def get(self, request: CredentialRequest) -> Credentials:
        with self._path.open() as f:
            entries: list[dict] = json.load(f)

        matches = [
            e
            for e in entries
            if e.get("service") == request.service
            and request.url in e.get("url", "")
            and (request.login is None or e.get("login") == request.login)
        ]

        if not matches:
            raise CredentialsNotFoundError(
                f"No credentials found for service={request.service!r} "
                f"url={request.url!r}"
            )
        if len(matches) > 1:
            warnings.warn(
                f"Multiple credentials found for service={request.service!r}; "
                "using first match",
                stacklevel=2,
            )
        entry = matches[0]
        return Credentials(login=entry["login"], password=entry["password"])


class JsonFileProviderFactory(CredentialProviderFactory):
    @property
    def provider_name(self) -> str:
        return "json"

    def add_cli_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--creds-json",
            metavar="PATH",
            help="Path to JSON credentials file",
        )

    def build_from_args(self, args: argparse.Namespace) -> CredentialProvider:
        if not args.creds_json:
            raise ValueError("--creds-json PATH is required for json provider")
        return JsonFileProvider(Path(args.creds_json))
