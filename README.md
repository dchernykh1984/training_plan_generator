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

This project requires **Python 3.14**; `uv` installs a matching interpreter automatically, but you can also install it yourself as shown below.

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

### 3. Install uv

**macOS / Linux**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows**

Open **PowerShell** and run:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Restart your terminal afterwards so `uv` is on your `PATH`.

### 4. Create virtual environment and install dependencies

```bash
uv sync
```

### 5. Set up pre-commit hooks

```bash
uv run pre-commit install
uv run pre-commit install --hook-type commit-msg
```

After that pre-commit hooks will run automatically on every commit.

To run all checks manually across all files:

```bash
uv run pre-commit run --all-files
```

## Usage

### Templates

Ready-to-edit starting points in the `templates/` folder:

| File | Description |
|---|---|
| [`templates/workout_garmin.json`](templates/workout_garmin.json) | Workout plan template (warmup, repeat block, cooldown; all target types) |
| [`templates/credentials.json`](templates/credentials.json) | JSON credentials file template for Garmin Connect |
| [`templates/keepass_entry.md`](templates/keepass_entry.md) | Guide for setting up the KeePass entry (Title, URL, Username, Password) |

### Graphical interface

Launch the GUI:

```bash
uv run training-plan-generator-gui
```

On Linux the Qt runtime needs a few system libraries; install them once if the GUI
fails to start with a `libEGL.so.1` error:

```bash
sudo apt install libegl1 libgl1 libxkbcommon0 libdbus-1-3
```

The window has two tabs:

- **Credentials** - add, edit and delete accounts. Each entry is either **manual**
  (login and password stored locally) or **KeePass** (only the path to the `.kdbx`
  file is stored).
- **Upload** - pick a plan file, then build a table of **upload targets**. Each row
  is one destination: a connector plus one of the credentials from the Credentials
  tab. Pressing **Upload** sends *every workout in the file* to *every target in the
  table*; progress and warnings appear in the log pane below the button.

There is no workout picker - the whole file is always uploaded. To upload a subset,
put those workouts in their own file.

Credentials, targets and the last-used plan path live in
`~/.config/training-plan-generator/` (`credentials.json`, `targets.json`,
`config.json`). **The KeePass master password is never written to disk** - it is
requested when an upload starts, held in memory for that run only, and discarded
when the run ends. If several targets read from the same `.kdbx` file, the password
is asked once per upload rather than once per target.

### Command-line upload

Copy and fill in the templates, then run:

```bash
uv run training-plan-generator upload \
  --plan templates/workout_garmin.json \
  --connector garmin \
  --credentials-provider json \
  --creds-json templates/credentials.json
```

Or with KeePass (see [`templates/keepass_entry.md`](templates/keepass_entry.md) for entry setup):

```bash
uv run training-plan-generator upload \
  --plan templates/workout_garmin.json \
  --connector garmin \
  --credentials-provider keepass \
  --creds-keepass /path/to/database.kdbx
```

The KeePass master password is read from `--keepass-password`, the `KEEPASS_PASSWORD`
environment variable, or prompted interactively.

Use `--login` to select a specific account when the credentials store has more than one
entry for the same service:

```bash
uv run training-plan-generator upload \
  --plan templates/workout_garmin.json \
  --connector garmin \
  --credentials-provider keepass \
  --creds-keepass /path/to/database.kdbx \
  --login your@email.com
```

### JSON plan format

A plan file contains either a **single workout** or a **list of workouts**. Every
workout in the file is uploaded - there is no way to select just one, so split the
file if you need a subset.

**Single workout** (a JSON object):

```json
{
  "name": "Morning Ride",
  "sport": "cycling",
  "steps": [...]
}
```

**Several workouts** (a JSON array of those same objects):

```json
[
  {
    "name": "Morning Ride",
    "sport": "cycling",
    "steps": [...]
  },
  {
    "name": "Evening Run",
    "sport": "running",
    "steps": [...]
  }
]
```

The two forms are interchangeable everywhere: a single object behaves exactly like a
one-element array. Both the CLI and the GUI log in once and then upload each workout
in order. If one workout fails the rest are still attempted, and the CLI exits with
status 1 to report the partial failure.

Workout names need not be unique, but the cache writes one file per name, so
identical names overwrite each other in `logs/workouts/`.

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
