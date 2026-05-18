from app.run_log import RunLogger


def test_info_appends_timestamped_line(tmp_path):
    logger = RunLogger(tmp_path)
    logger.info("plan loaded")
    content = (tmp_path / "training_plan_generator.log").read_text()
    assert "INFO" in content
    assert "plan loaded" in content


def test_warning_appends_timestamped_line(tmp_path):
    logger = RunLogger(tmp_path)
    logger.warning("cadence dropped")
    content = (tmp_path / "training_plan_generator.log").read_text()
    assert "WARNING" in content
    assert "cadence dropped" in content


def test_error_appends_timestamped_line(tmp_path):
    logger = RunLogger(tmp_path)
    logger.error("login failed")
    content = (tmp_path / "training_plan_generator.log").read_text()
    assert "ERROR" in content
    assert "login failed" in content


def test_log_created_if_absent(tmp_path):
    log_path = tmp_path / "training_plan_generator.log"
    assert not log_path.exists()
    RunLogger(tmp_path).info("start")
    assert log_path.exists()


def test_log_appended_across_instances(tmp_path):
    RunLogger(tmp_path).info("first")
    RunLogger(tmp_path).info("second")
    lines = (tmp_path / "training_plan_generator.log").read_text().splitlines()
    assert len(lines) == 2
    assert "first" in lines[0]
    assert "second" in lines[1]


def test_log_line_format(tmp_path):
    RunLogger(tmp_path).info("test message")
    line = (tmp_path / "training_plan_generator.log").read_text().strip()
    parts = line.split(" ", 2)
    assert len(parts) == 3
    ts, level, msg = parts
    assert "T" in ts
    assert level == "INFO"
    assert msg == "test message"
