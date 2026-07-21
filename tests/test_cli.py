from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.cli import _build_parser, _cmd_upload

_VALID_PLAN = {
    "name": "3x8 Cycling Intervals",
    "sport": "cycling",
    "steps": [
        {
            "type": "warmup",
            "duration_seconds": 600,
            "targets": [{"type": "power", "low": 130, "high": 170}],
        },
    ],
}

_GARMIN_CREDS = [
    {"service": "garmin", "url": "garmin", "login": "u@t.com", "password": "pw"}
]


def _write_garmin_creds(tmp_path):
    p = tmp_path / "creds.json"
    p.write_text(json.dumps(_GARMIN_CREDS))
    return p


def _plan_file(tmp_path, data=None):
    p = tmp_path / "plan.json"
    p.write_text(json.dumps(data or _VALID_PLAN))
    return p


def _upload_args(
    tmp_path,
    plan=None,
    connector="garmin",
    provider="json",
    cache_dir=None,
    creds_json=None,
    creds_keepass=None,
    keepass_password=None,
    login=None,
    workout_key=None,
):
    import argparse

    ns = argparse.Namespace(
        command="upload",
        plan=str(plan or _plan_file(tmp_path)),
        connector=connector,
        credentials_provider=provider,
        cache_dir=str(cache_dir or tmp_path / "cache"),
        creds_json=creds_json,
        creds_keepass=creds_keepass,
        keepass_password=keepass_password,
        login=login,
        workout_key=workout_key,
    )
    return ns


def test_parser_exposes_only_upload_subcommand(tmp_path):
    parser = _build_parser()
    creds_file = _write_garmin_creds(tmp_path)
    plan = _plan_file(tmp_path)
    args = parser.parse_args(
        [
            "upload",
            "--plan",
            str(plan),
            "--connector",
            "garmin",
            "--credentials-provider",
            "json",
            "--creds-json",
            str(creds_file),
        ]
    )
    assert args.command == "upload"

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "generate",
                "--plan",
                str(plan),
                "--format",
                "fit",
                "--output",
                "x.fit",
            ]
        )


def test_upload_valid_plan_calls_connector_and_caches(tmp_path):
    creds_file = _write_garmin_creds(tmp_path)
    args = _upload_args(tmp_path, creds_json=str(creds_file))

    mock_connector = MagicMock()
    mock_connector.upload.return_value = "workout-42"

    with patch("app.cli.get_connector", return_value=mock_connector):
        result = _cmd_upload(args)

    assert result == 0
    mock_connector.login.assert_called_once()
    mock_connector.upload.assert_called_once()
    cache = tmp_path / "cache" / "workouts"
    assert any(".garmin.json" in f.name for f in cache.iterdir())


def test_upload_caches_source_and_payload(tmp_path):
    creds_file = _write_garmin_creds(tmp_path)
    args = _upload_args(tmp_path, creds_json=str(creds_file))

    mock_connector = MagicMock()
    mock_connector.upload.return_value = "w-1"

    with patch("app.cli.get_connector", return_value=mock_connector):
        result = _cmd_upload(args)

    assert result == 0
    files = {f.name for f in (tmp_path / "cache" / "workouts").iterdir()}
    assert any(".garmin.json" in n for n in files)
    assert any(".source.json" in n for n in files)


def test_upload_unknown_connector_rejects(tmp_path):
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "upload",
                "--plan",
                "x.json",
                "--connector",
                "polar",
                "--credentials-provider",
                "json",
            ]
        )


def test_upload_unknown_provider_rejects(tmp_path):
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "upload",
                "--plan",
                "x.json",
                "--connector",
                "garmin",
                "--credentials-provider",
                "vault",
            ]
        )


def test_upload_logs_login_and_upload_result(tmp_path):
    creds_file = _write_garmin_creds(tmp_path)
    args = _upload_args(tmp_path, creds_json=str(creds_file))

    mock_connector = MagicMock()
    mock_connector.upload.return_value = "12345"

    with patch("app.cli.get_connector", return_value=mock_connector):
        _cmd_upload(args)

    log = (tmp_path / "cache" / "training_plan_generator.log").read_text()
    assert "login success" in log
    assert "upload success" in log
    assert "12345" in log
    assert "pw" not in log


def test_upload_login_failure_returns_error(tmp_path):
    creds_file = _write_garmin_creds(tmp_path)
    args = _upload_args(tmp_path, creds_json=str(creds_file))

    mock_connector = MagicMock()
    mock_connector.login.side_effect = RuntimeError("auth failed")

    with patch("app.cli.get_connector", return_value=mock_connector):
        result = _cmd_upload(args)

    assert result == 1
    log = (tmp_path / "cache" / "training_plan_generator.log").read_text()
    assert "login error" in log
    assert "pw" not in log


def test_upload_missing_plan_file_returns_error(tmp_path):
    args = _upload_args(tmp_path, plan=tmp_path / "nonexistent.json")
    result = _cmd_upload(args)
    assert result == 1
    log = (tmp_path / "cache" / "training_plan_generator.log").read_text()
    assert "plan read error" in log


def test_upload_missing_creds_json_returns_error(tmp_path):
    args = _upload_args(tmp_path, creds_json=None)
    result = _cmd_upload(args)
    assert result == 1


def test_upload_invalid_plan_json_returns_error(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{{{not json")
    args = _upload_args(tmp_path, plan=bad)
    result = _cmd_upload(args)
    assert result == 1


def test_upload_connector_upload_failure_returns_error(tmp_path):
    creds_file = _write_garmin_creds(tmp_path)
    args = _upload_args(tmp_path, creds_json=str(creds_file))

    mock_connector = MagicMock()
    mock_connector.upload.side_effect = RuntimeError("upload failed")

    with patch("app.cli.get_connector", return_value=mock_connector):
        result = _cmd_upload(args)

    assert result == 1
    log = (tmp_path / "cache" / "training_plan_generator.log").read_text()
    assert "upload error" in log


def test_upload_target_drop_warning_appears_in_log(tmp_path):
    plan_data = {
        "name": "Test Plan",
        "sport": "cycling",
        "steps": [
            {
                "type": "interval",
                "duration_seconds": 300,
                "targets": [
                    {"type": "power", "low": 200, "high": 250},
                    {"type": "cadence", "low": 85, "high": 95},
                    {"type": "heart_rate", "low": 150, "high": 165},
                ],
            }
        ],
    }
    creds_file = _write_garmin_creds(tmp_path)
    args = _upload_args(
        tmp_path, plan=_plan_file(tmp_path, data=plan_data), creds_json=str(creds_file)
    )
    mock_connector = MagicMock()
    mock_connector.upload.return_value = "42"
    with patch("app.cli.get_connector", return_value=mock_connector):
        result = _cmd_upload(args)
    assert result == 0
    log = (tmp_path / "cache" / "training_plan_generator.log").read_text()
    assert "WARNING" in log
    assert "dropped" in log


def test_main_upload(tmp_path):
    creds_file = _write_garmin_creds(tmp_path)
    plan = _plan_file(tmp_path)
    argv = [
        "training-plan-generator",
        "upload",
        "--plan",
        str(plan),
        "--connector",
        "garmin",
        "--credentials-provider",
        "json",
        "--creds-json",
        str(creds_file),
        "--cache-dir",
        str(tmp_path / "cache"),
    ]
    mock_connector = MagicMock()
    mock_connector.upload.return_value = "99"
    with (
        patch("sys.argv", argv),
        patch("app.cli.get_connector", return_value=mock_connector),
    ):
        with pytest.raises(SystemExit) as exc:
            from app.cli import main

            main()
    assert exc.value.code == 0


def test_parser_accepts_login_flag(tmp_path):
    parser = _build_parser()
    creds_file = _write_garmin_creds(tmp_path)
    plan = _plan_file(tmp_path)
    args = parser.parse_args(
        [
            "upload",
            "--plan",
            str(plan),
            "--connector",
            "garmin",
            "--credentials-provider",
            "json",
            "--creds-json",
            str(creds_file),
            "--login",
            "me@example.com",
        ]
    )
    assert args.login == "me@example.com"


def test_upload_login_flag_filters_credentials(tmp_path):
    creds = [
        {
            "service": "garmin",
            "url": "garmin",
            "login": "a@test.com",
            "password": "pw1",
        },
        {
            "service": "garmin",
            "url": "garmin",
            "login": "b@test.com",
            "password": "pw2",
        },
    ]
    creds_file = tmp_path / "creds.json"
    creds_file.write_text(json.dumps(creds))
    args = _upload_args(tmp_path, creds_json=str(creds_file), login="b@test.com")

    mock_connector = MagicMock()
    mock_connector.upload.return_value = "42"

    with patch("app.cli.get_connector", return_value=mock_connector):
        result = _cmd_upload(args)

    assert result == 0
    used_creds = mock_connector.login.call_args[0][0]
    assert used_creds.login == "b@test.com"


def test_parser_build_succeeds():
    parser = _build_parser()
    assert parser is not None


# --- multi-workout file support ---

_MULTI_PLAN = {
    "morning": {
        "name": "Morning Ride",
        "sport": "cycling",
        "steps": [{"type": "warmup", "duration_seconds": 300}],
    },
    "evening": {
        "name": "Evening Run",
        "sport": "running",
        "steps": [{"type": "cooldown", "duration_seconds": 600}],
    },
}


def test_upload_multi_workout_with_key_succeeds(tmp_path):
    creds_file = _write_garmin_creds(tmp_path)
    plan_file = tmp_path / "multi.json"
    plan_file.write_text(json.dumps(_MULTI_PLAN))
    args = _upload_args(
        tmp_path,
        plan=plan_file,
        creds_json=str(creds_file),
        workout_key="morning",
    )
    mock_connector = MagicMock()
    mock_connector.upload.return_value = "w-multi"
    with patch("app.cli.get_connector", return_value=mock_connector):
        result = _cmd_upload(args)
    assert result == 0
    mock_connector.upload.assert_called_once()


def test_upload_multi_workout_no_key_returns_error(tmp_path):
    creds_file = _write_garmin_creds(tmp_path)
    plan_file = tmp_path / "multi.json"
    plan_file.write_text(json.dumps(_MULTI_PLAN))
    args = _upload_args(tmp_path, plan=plan_file, creds_json=str(creds_file))
    result = _cmd_upload(args)
    assert result == 1


def test_upload_multi_workout_wrong_key_returns_error(tmp_path):
    creds_file = _write_garmin_creds(tmp_path)
    plan_file = tmp_path / "multi.json"
    plan_file.write_text(json.dumps(_MULTI_PLAN))
    args = _upload_args(
        tmp_path,
        plan=plan_file,
        creds_json=str(creds_file),
        workout_key="nonexistent",
    )
    result = _cmd_upload(args)
    assert result == 1


def test_upload_single_workout_ignores_workout_key(tmp_path):
    creds_file = _write_garmin_creds(tmp_path)
    args = _upload_args(tmp_path, creds_json=str(creds_file), workout_key="any")
    mock_connector = MagicMock()
    mock_connector.upload.return_value = "w-1"
    with patch("app.cli.get_connector", return_value=mock_connector):
        result = _cmd_upload(args)
    assert result == 0


def test_parser_accepts_workout_key_flag(tmp_path):
    parser = _build_parser()
    creds_file = _write_garmin_creds(tmp_path)
    plan = _plan_file(tmp_path)
    args = parser.parse_args(
        [
            "upload",
            "--plan",
            str(plan),
            "--connector",
            "garmin",
            "--credentials-provider",
            "json",
            "--creds-json",
            str(creds_file),
            "--workout-key",
            "morning",
        ]
    )
    assert args.workout_key == "morning"
