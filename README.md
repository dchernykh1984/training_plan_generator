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

### Upload to Garmin Connect

```bash
poetry run training-plan-generator upload \
  --plan examples/cycling_intervals.json \
  --connector garmin \
  --credentials-provider json \
  --creds-json /path/to/credentials.json
```

Or with KeePass:

```bash
poetry run training-plan-generator upload \
  --plan examples/cycling_intervals.json \
  --connector garmin \
  --credentials-provider keepass \
  --creds-keepass /path/to/database.kdbx
```

The KeePass master password is read from `--keepass-password`, the `KEEPASS_PASSWORD`
environment variable, or prompted interactively.

### JSON plan format

```json
{
  "name": "Workout name",
  "sport": "cycling",
  "steps": [
    {"type": "warmup",   "duration_seconds": 600,
     "targets": [{"type": "power", "low": 130, "high": 170}]},
    {
      "type": "repeat", "count": 3,
      "steps": [
        {"type": "interval", "duration_seconds": 480,
         "targets": [
           {"type": "power",      "low": 260, "high": 300},
           {"type": "cadence",    "low": 88,  "high": 92},
           {"type": "heart_rate", "low": 155, "high": 165}
         ]},
        {"type": "rest", "duration_seconds": 240,
         "targets": [{"type": "power", "low": 90, "high": 110}]}
      ]
    },
    {"type": "cooldown", "duration_seconds": 300,
     "targets": [{"type": "power", "low": 90, "high": 120}]}
  ]
}
```

Supported sports: `cycling`, `running`, `swimming`.
Supported step types: `warmup`, `cooldown`, `interval`, `rest`, `repeat`.
Supported target types: `power` (watts), `heart_rate` (bpm), `cadence` (rpm).
Each step accepts 0-3 targets (at most one of each type).

**Note:** Garmin Connect supports at most 2 targets per step. When a
step has 3 targets, the adapter keeps `power` and `heart_rate` (by priority) and drops
`cadence`, printing a warning and writing it to the run log.

### JSON credentials file format

```json
[
  {
    "service": "garmin",
    "url": "https://connect.garmin.com",
    "login": "user@example.com",
    "password": "yourpassword"
  }
]
```

### Cache and log

Uploaded workouts and the execution log are stored under the cache directory
(default: `~/.training_plan_generator/cache`):

```
~/.training_plan_generator/cache/
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
