# KeePass entry setup

Create one entry in your `.kdbx` database per training service.
The tool matches entries by **Title** and **URL**, so these two fields are critical.

## Required fields

| KeePass field | Value for Garmin Connect |
|---|---|
| Title | `garmin` |
| URL | `https://connect.garmin.com` (any value containing this substring) |
| Username | your Garmin Connect e-mail |
| Password | your Garmin Connect password |

The **Title** must match the connector name passed to `--connector`.
The **URL** is matched as a substring, so `https://connect.garmin.com` and
`connect.garmin.com` both work.

## Usage

```bash
poetry run training-plan-generator upload \
  --plan templates/workout_garmin.json \
  --connector garmin \
  --credentials-provider keepass \
  --creds-keepass /path/to/database.kdbx
```

The master password is read from:
1. `--keepass-password PASSWORD` CLI flag
2. `KEEPASS_PASSWORD` environment variable
3. Interactive prompt (if neither of the above is set)
