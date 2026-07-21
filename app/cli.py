from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from app.cache import WorkoutCache
from app.connectors.registry import CONNECTORS, get_adapter, get_connector
from app.credentials.base import CredentialRequest
from app.credentials.registry import PROVIDER_FACTORIES, get_factory
from app.run_log import RunLogger

if TYPE_CHECKING:
    from app.connectors.base import WorkoutConnector
    from app.models.workout import WorkoutPlan

_DEFAULT_CACHE_DIR = Path("logs")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="training-plan-generator",
        description="Upload structured workout plans to training services",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    up = sub.add_parser("upload", help="Upload a workout to a training service")
    up.add_argument(
        "--plan", required=True, metavar="PATH", help="Path to workout JSON file"
    )
    up.add_argument(
        "--cache-dir",
        metavar="PATH",
        default=str(_DEFAULT_CACHE_DIR),
        help="Cache directory (default: ./logs)",
    )
    up.add_argument(
        "--connector",
        required=True,
        choices=sorted(CONNECTORS),
        help="Training service connector",
    )
    up.add_argument(
        "--credentials-provider",
        required=True,
        dest="credentials_provider",
        choices=sorted(PROVIDER_FACTORIES),
        help="Credentials provider",
    )
    up.add_argument(
        "--login",
        metavar="LOGIN",
        default=None,
        help=(
            "Filter credentials by login"
            " (useful when multiple accounts exist for one service)"
        ),
    )
    for factory in PROVIDER_FACTORIES.values():
        factory.add_cli_args(up)

    return parser


def _cmd_upload(args: argparse.Namespace) -> int:
    from app.models.parser import parse_workout_file

    cache_dir = Path(args.cache_dir)
    log = RunLogger(cache_dir)
    cache = WorkoutCache(cache_dir)

    log.info(
        f"upload start: plan={args.plan} connector={args.connector} "
        f"provider={args.credentials_provider}"
    )
    print(f"Loading plan: {Path(args.plan).name}")

    try:
        source_bytes = Path(args.plan).read_bytes()
    except OSError as e:
        print(f"Error: {e}", file=sys.stderr)
        log.error(f"plan read error: {e}")
        return 1

    try:
        plans = parse_workout_file(json.loads(source_bytes))
    except (ValueError, json.JSONDecodeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        log.error(f"parse error: {e}")
        return 1

    log.info(f"plan loaded: {len(plans)} workout(s)")
    print(f"Loaded {len(plans)} workout(s).")

    # One source snapshot per run - it covers every workout in the file.
    src_path = cache.save_source_plan(Path(args.plan).stem, source_bytes)
    log.info(f"source cached: {src_path}")

    print(f"Reading credentials ({args.credentials_provider})...")
    try:
        factory = get_factory(args.credentials_provider)
        provider = factory.build_from_args(args)
        request = CredentialRequest(
            service=args.connector, url=args.connector, login=args.login
        )
        creds = provider.get(request)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        log.error(f"credentials error: {e}")
        return 1

    log.info(
        f"credentials loaded: provider={args.credentials_provider} "
        f"login={creds.login!r}"
    )

    print(f"Logging in to {args.connector} ({creds.login})...")
    connector = get_connector(args.connector)
    _garmin_logger = logging.getLogger("garminconnect.client")
    _orig_level = _garmin_logger.level
    _garmin_logger.setLevel(logging.ERROR)
    try:
        connector.login(creds)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        log.error(f"login error: {e}")
        return 1
    finally:
        _garmin_logger.setLevel(_orig_level)

    log.info("login success")

    failed = 0
    for plan in plans:
        if not _upload_one(plan, connector, cache, args, log):
            failed += 1

    uploaded = len(plans) - failed
    print(f"Done: {uploaded}/{len(plans)} workout(s) uploaded to {args.connector}.")
    print(f"Log:    {cache_dir / 'training_plan_generator.log'}")
    return 1 if failed else 0


def _upload_one(
    plan: WorkoutPlan,
    connector: WorkoutConnector,
    cache: WorkoutCache,
    args: argparse.Namespace,
    log: RunLogger,
) -> bool:
    """Build, upload and cache a single workout. Returns True on success."""
    log.info(f"plan: name={plan.name!r} sport={plan.sport} steps={len(plan.steps)}")
    print(f"Building {args.connector} payload for {plan.name!r}...")
    adapter = get_adapter(args.connector)
    adapt_result = adapter.to_payload(plan)
    for w in adapt_result.warnings:
        print(f"Warning: {w}")
        log.warning(w)
    payload = adapt_result.payload

    print(f'Uploading workout "{plan.name}"...')
    try:
        workout_id = connector.upload(payload)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        log.error(f"upload error for {plan.name!r}: {e}")
        return False

    log.info(f"upload success: name={plan.name!r} id={workout_id}")
    payload_path = cache.save_connector_payload(plan.name, args.connector, payload)
    print(f"Cached: {payload_path}")
    log.info(f"artifacts saved: payload={payload_path}")
    return True


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    sys.exit(_cmd_upload(args))


if __name__ == "__main__":  # pragma: no cover
    main()
