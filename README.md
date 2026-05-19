# training-plan-generator

CLI tool for uploading structured workout plans to training services.

## Setup

### 1. Download the project

Install Git if you don't have it:

- **macOS:** `brew install git`
- **Linux (Ubuntu / Debian):** `sudo apt install git`
- **Windows:** download from [git-scm.com](https://git-scm.com/downloads) and run the installer

Then clone the repository:

```bash
git clone https://github.com/dchernykh1984/training_plan_generator.git
cd training_plan_generator
```

All subsequent commands should be run from the `training_plan_generator` folder.

### 2. Install Python 3.14

This project requires **Python 3.14**. Installing a different version will result in an error when running `poetry install`.

**macOS**

```bash
brew install python@3.14
```

If you don't have Homebrew yet, install it first from [brew.sh](https://brew.sh).

**Linux (Ubuntu / Debian)**

The system `python3` package is usually not 3.14. Install it via the deadsnakes PPA:

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.14 python3.14-venv
```

**Windows**

Download the **Python 3.14** installer from [python.org/downloads](https://www.python.org/downloads/) and run it. On the first screen, check **"Add Python to PATH"** before clicking Install.

Verify the installation in a terminal:

- **macOS / Linux:** `python3.14 --version`
- **Windows:** `py -3.14 --version`

The output should start with `Python 3.14`.

### 3. Install Poetry

**macOS**

```bash
brew install pipx
pipx ensurepath
pipx install poetry
```

**Linux (Ubuntu / Debian)**

```bash
pip3 install pipx
pipx ensurepath
pipx install poetry
```

Restart your terminal after running `pipx ensurepath`.

**Windows**

Open **Command Prompt** or **PowerShell** and run:

```powershell
pip install pipx
pipx ensurepath
pipx install poetry
```

Restart your terminal after running `pipx ensurepath`.

### 4. Create virtual environment and install dependencies

```bash
poetry config virtualenvs.in-project true
poetry install
```

### 5. Set up pre-commit hooks

```bash
poetry run pre-commit install
poetry run pre-commit install --hook-type commit-msg
```

After that pre-commit hooks will run automatically on every commit.

To run all checks manually across all files:

```bash
poetry run pre-commit run --all-files
```

## Usage

### Templates

Ready-to-edit starting points in the `templates/` folder:

| File | Description |
|---|---|
| [`templates/workout_garmin.json`](templates/workout_garmin.json) | Workout plan template (warmup, repeat block, cooldown; all target types) |
| [`templates/credentials.json`](templates/credentials.json) | JSON credentials file template for Garmin Connect |
| [`templates/keepass_entry.md`](templates/keepass_entry.md) | Guide for setting up the KeePass entry (Title, URL, Username, Password) |

### Upload to Garmin Connect

Copy and fill in the templates, then run:

```bash
poetry run training-plan-generator upload \
  --plan templates/workout_garmin.json \
  --connector garmin \
  --credentials-provider json \
  --creds-json templates/credentials.json
```

Or with KeePass (see [`templates/keepass_entry.md`](templates/keepass_entry.md) for entry setup):

```bash
poetry run training-plan-generator upload \
  --plan templates/workout_garmin.json \
  --connector garmin \
  --credentials-provider keepass \
  --creds-keepass /path/to/database.kdbx
```

The KeePass master password is read from `--keepass-password`, the `KEEPASS_PASSWORD`
environment variable, or prompted interactively.

### JSON plan format

See [`templates/workout_garmin.json`](templates/workout_garmin.json) for a ready-to-edit example.

**Plan-level fields**

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Workout name |
| `sport` | string | yes | `cycling`, `running`, or `swimming` |
| `description` | string | no | Free-text description; surfaces in Garmin payload |
| `ftp_watts` | integer | no | Athlete's FTP in watts (positive) |
| `estimated_tss` | number | no | Estimated Training Stress Score (&gt;= 0) |

**Step fields**

| Field | Type | Default | Description |
|---|---|---|---|
| `type` | string | - | `warmup`, `cooldown`, `interval`, `rest`, or `repeat` |
| `name` | string | `""` | Optional step label; appears as `stepDescription` in Garmin |
| `duration_type` | string | `"time"` | `time`, `distance`, or `open` |
| `duration_seconds` | integer | - | Seconds when `time`; **meters** when `distance`; absent/null when `open` |

**Duration types**

- `time` - step ends after the given number of seconds.
- `distance` - step ends after the given number of **meters** (field name `duration_seconds` is reused).
- `open` - step ends on manual lap-button press; `duration_seconds` must be absent or null.

**Targets**

Supported target types: `power` (watts), `heart_rate` (bpm), `cadence` (rpm).
Each step accepts 0-3 targets (at most one per type).

Valid value ranges:

| Target | Min | Max |
|---|---|---|
| `power` | 0 | 2500 W |
| `heart_rate` | 20 | 250 bpm |
| `cadence` | 0 | 220 rpm |

**Garmin-specific notes**

- Garmin Connect supports at most 2 targets per step. Target priority is
  `power` > `heart_rate` > `cadence`. When a step has 3 targets the lowest-priority
  one is dropped and a warning is written to the run log.
- `repeat` steps may not be nested (maximum nesting depth is 1).
- If the total expanded step count exceeds 50, a warning is written to the run log
  and the upload is still attempted.

### Adapter warning/fallback contract

Adapters return warnings in `AdapterResult.warnings` rather than raising exceptions
when they encounter unsupported optional parameters:

- Unsupported target type -&gt; target skipped, warning added.
- Unsupported `duration_type` -&gt; fallback applied, warning added.
- Service limit exceeded (e.g. step count) -&gt; upload still attempted, warning added.

Warnings are printed to stdout and written to the run log by the CLI.

### JSON credentials file format

See [`templates/credentials.json`](templates/credentials.json).

### Cache and log

Uploaded workouts and the execution log are stored under the cache directory
(default: `./logs` in the current working directory):

```
logs/
  workouts/
    <slug>.garmin.json          Garmin payload
    <slug>.source.json          original source plan JSON
  training_plan_generator.log   append log across all runs
```

Override the cache directory with `--cache-dir PATH`.

### Extending the tool

Adding a new connector requires a payload adapter, a connector, and two registry
entries; adding a credential provider requires a provider/factory and one registry
entry. No changes to CLI, cache, or orchestration are needed in either case:

- **New connector:** implement `PayloadAdapter` (workout plan -> service JSON) in
  `app/adapters/` and `WorkoutConnector` (auth + upload) in `app/connectors/`, then
  add both to `CONNECTORS` / `PAYLOAD_ADAPTERS` in `app/connectors/registry.py`.
- **New credential provider:** implement `CredentialProvider` and
  `CredentialProviderFactory` in `app/credentials/`, add the factory instance to
  `PROVIDER_FACTORIES` in `app/credentials/registry.py`. The factory's
  `add_cli_args()` method registers any provider-specific CLI flags automatically.

## Contributing

Before requesting a review, make sure the CI pipeline passes on your pull request. Once the pipeline is green, request a review from [@dchernykh1984](https://github.com/dchernykh1984).
