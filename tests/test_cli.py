from __future__ import annotations

import datetime
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
    output_dir=None,
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
        output_dir=output_dir,
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


def test_upload_to_intervals_caches_its_payload(tmp_path):
    creds = [
        {
            "service": "intervals",
            "url": "https://intervals.icu",
            "login": "me",
            "password": "key",
        }
    ]
    creds_file = tmp_path / "creds.json"
    creds_file.write_text(json.dumps(creds))
    args = _build_parser().parse_args(
        [
            "upload",
            "--plan",
            str(_plan_file(tmp_path)),
            "--connector",
            "intervals",
            "--credentials-provider",
            "json",
            "--creds-json",
            str(creds_file),
            "--cache-dir",
            str(tmp_path / "cache"),
        ]
    )

    mock_connector = MagicMock()
    mock_connector.upload.return_value = "42"
    with patch("app.cli.get_connector", return_value=mock_connector):
        assert _cmd_upload(args) == 0

    payload = mock_connector.upload.call_args.args[0]
    assert payload["type"] == "Ride"
    assert payload["description"].startswith("- 10m 130-170w")
    files = {f.name for f in (tmp_path / "cache" / "workouts").iterdir()}
    assert "3x8_cycling_intervals.intervals.json" in files


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

_MULTI_PLAN = [
    {
        "name": "Morning Ride",
        "sport": "cycling",
        "steps": [{"type": "warmup", "duration_seconds": 300}],
    },
    {
        "name": "Evening Run",
        "sport": "running",
        "steps": [{"type": "cooldown", "duration_seconds": 600}],
    },
]


def _multi_plan_file(tmp_path):
    plan_file = tmp_path / "multi.json"
    plan_file.write_text(json.dumps(_MULTI_PLAN))
    return plan_file


def test_upload_multi_workout_uploads_every_workout(tmp_path):
    creds_file = _write_garmin_creds(tmp_path)
    args = _upload_args(
        tmp_path, plan=_multi_plan_file(tmp_path), creds_json=str(creds_file)
    )
    mock_connector = MagicMock()
    mock_connector.upload.return_value = "w-multi"
    with patch("app.cli.get_connector", return_value=mock_connector):
        result = _cmd_upload(args)
    assert result == 0
    assert mock_connector.upload.call_count == 2


def test_upload_multi_workout_logs_in_only_once(tmp_path):
    creds_file = _write_garmin_creds(tmp_path)
    args = _upload_args(
        tmp_path, plan=_multi_plan_file(tmp_path), creds_json=str(creds_file)
    )
    mock_connector = MagicMock()
    mock_connector.upload.return_value = "w-multi"
    with patch("app.cli.get_connector", return_value=mock_connector):
        _cmd_upload(args)
    mock_connector.login.assert_called_once()


def test_upload_multi_workout_caches_each_workout(tmp_path):
    creds_file = _write_garmin_creds(tmp_path)
    cache_dir = tmp_path / "cache"
    args = _upload_args(
        tmp_path,
        plan=_multi_plan_file(tmp_path),
        creds_json=str(creds_file),
        cache_dir=cache_dir,
    )
    mock_connector = MagicMock()
    mock_connector.upload.return_value = "w-multi"
    with patch("app.cli.get_connector", return_value=mock_connector):
        _cmd_upload(args)
    cached = {p.name for p in (cache_dir / "workouts").iterdir()}
    assert any("morning" in n for n in cached)
    assert any("evening" in n for n in cached)


def test_upload_multi_workout_saves_one_source_snapshot(tmp_path):
    """The whole file is one source artifact, not one copy per workout."""
    creds_file = _write_garmin_creds(tmp_path)
    cache_dir = tmp_path / "cache"
    args = _upload_args(
        tmp_path,
        plan=_multi_plan_file(tmp_path),
        creds_json=str(creds_file),
        cache_dir=cache_dir,
    )
    mock_connector = MagicMock()
    mock_connector.upload.return_value = "w-multi"
    with patch("app.cli.get_connector", return_value=mock_connector):
        _cmd_upload(args)
    sources = [
        p.name for p in (cache_dir / "workouts").iterdir() if ".source." in p.name
    ]
    assert sources == ["multi.source.json"]


def test_upload_multi_workout_partial_failure_returns_error(tmp_path):
    creds_file = _write_garmin_creds(tmp_path)
    args = _upload_args(
        tmp_path, plan=_multi_plan_file(tmp_path), creds_json=str(creds_file)
    )
    mock_connector = MagicMock()
    mock_connector.upload.side_effect = ["w-1", RuntimeError("boom")]
    with patch("app.cli.get_connector", return_value=mock_connector):
        result = _cmd_upload(args)
    assert result == 1
    # The first workout must still have been attempted and uploaded.
    assert mock_connector.upload.call_count == 2


def test_upload_single_workout_object_still_works(tmp_path):
    creds_file = _write_garmin_creds(tmp_path)
    args = _upload_args(tmp_path, creds_json=str(creds_file))
    mock_connector = MagicMock()
    mock_connector.upload.return_value = "w-1"
    with patch("app.cli.get_connector", return_value=mock_connector):
        result = _cmd_upload(args)
    assert result == 0
    mock_connector.upload.assert_called_once()


def test_upload_empty_list_returns_error(tmp_path):
    creds_file = _write_garmin_creds(tmp_path)
    plan_file = tmp_path / "empty.json"
    plan_file.write_text("[]")
    args = _upload_args(tmp_path, plan=plan_file, creds_json=str(creds_file))
    assert _cmd_upload(args) == 1


def test_upload_passes_the_plan_date_to_the_connector(tmp_path, capsys):
    creds_file = _write_garmin_creds(tmp_path)
    plan = _plan_file(tmp_path, {**_VALID_PLAN, "date": "2026-11-20"})
    args = _upload_args(tmp_path, plan=plan, creds_json=str(creds_file))
    mock_connector = MagicMock()
    mock_connector.upload.return_value = "w-1"

    with patch("app.cli.get_connector", return_value=mock_connector):
        assert _cmd_upload(args) == 0

    assert mock_connector.upload.call_args.args[1] == datetime.date(2026, 11, 20)
    assert '3x8 Cycling Intervals" for 2026-11-20...' in capsys.readouterr().out


_ZWIFT_PLAN = {**_VALID_PLAN, "ftp_watts": 260}


def test_upload_to_zwift_needs_no_credentials(tmp_path, capsys):
    out = tmp_path / "zwift"
    out.mkdir()
    args = _build_parser().parse_args(
        [
            "upload",
            "--plan",
            str(_plan_file(tmp_path, _ZWIFT_PLAN)),
            "--connector",
            "zwift",
            "--output-dir",
            str(out),
            "--cache-dir",
            str(tmp_path / "cache"),
        ]
    )

    assert _cmd_upload(args) == 0

    zwo = (out / "3x8_cycling_intervals.zwo").read_text()
    assert '<Warmup Duration="600" PowerLow="0.577" PowerHigh="0.577" />' in zwo
    assert f"Writing .zwo files to {out}" in capsys.readouterr().out


def test_upload_to_a_missing_folder_fails(tmp_path, capsys):
    args = _upload_args(
        tmp_path, connector="zwift", provider=None, output_dir=str(tmp_path / "no")
    )
    assert _cmd_upload(args) == 1
    err = capsys.readouterr().err
    assert "Folder not found" in err
    assert "--output-dir" not in err  # the folder was chosen; it is just missing


def test_output_dir_is_only_for_file_connectors(tmp_path, capsys):
    args = _upload_args(tmp_path, output_dir=str(tmp_path))
    assert _cmd_upload(args) == 1
    assert "--output-dir is only for connectors that write files" in (
        capsys.readouterr().err
    )


def test_a_service_connector_needs_a_credentials_provider(tmp_path, capsys):
    args = _upload_args(tmp_path, provider=None)
    assert _cmd_upload(args) == 1
    assert "--credentials-provider is required for garmin" in capsys.readouterr().err


def test_a_plan_the_connector_cannot_take_fails_alone(tmp_path, capsys):
    plans = [{**_ZWIFT_PLAN, "sport": "running"}, {**_ZWIFT_PLAN, "name": "Ride"}]
    args = _upload_args(
        tmp_path,
        plan=_plan_file(tmp_path, plans),
        connector="zwift",
        provider=None,
        output_dir=str(tmp_path),
    )

    assert _cmd_upload(args) == 1

    assert "Zwift workouts are rides" in capsys.readouterr().err
    assert (tmp_path / "ride.zwo").exists()


def test_erg_files_need_an_output_dir(tmp_path, capsys):
    args = _upload_args(tmp_path, connector="erg-file", provider=None)
    assert _cmd_upload(args) == 1
    assert (
        "Error: Choose the folder to write .erg files to (pass --output-dir PATH)"
        in capsys.readouterr().err
    )


def test_upload_writes_an_erg_file(tmp_path):
    args = _upload_args(
        tmp_path, connector="erg-file", provider=None, output_dir=str(tmp_path)
    )
    assert _cmd_upload(args) == 0
    assert (
        "0.00\t150\n10.00\t150\n"
        in (tmp_path / "3x8_cycling_intervals.erg").read_text()
    )


def test_upload_writes_a_fit_file(tmp_path):
    plan = _plan_file(tmp_path, {**_VALID_PLAN, "date": "2026-11-20"})
    args = _upload_args(
        tmp_path,
        plan=plan,
        connector="fit-file",
        provider=None,
        output_dir=str(tmp_path),
    )
    assert _cmd_upload(args) == 0
    data = (tmp_path / "2026-11-20_3x8_cycling_intervals.fit").read_bytes()
    assert data[8:12] == b".FIT"
