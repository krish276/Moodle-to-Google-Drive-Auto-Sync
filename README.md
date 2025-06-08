# Moodle to Google Drive Auto-Sync

This project provides a Python script that logs into a Moodle instance,
detects newly uploaded course files and mirrors them to Google Drive.
Synced files are tracked using a local SQLite database so repeated runs
only upload new materials.

## Requirements

- Python 3.9+
- Google service account credentials for Drive API
- ChromeDriver installed and available in `PATH`
- See `requirements.txt` for Python packages

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Create a `.env` file or export the following environment variables:
   - `MOODLE_LOGIN_URL` – URL of the Moodle login page
   - `MOODLE_USERNAME` and `MOODLE_PASSWORD`
   - `GOOGLE_SERVICE_ACCOUNT_FILE` – path to a service account JSON file
   - `DRIVE_ROOT` – (optional) name of the root folder in Drive
3. Run the sync script:
   ```bash
   python sync.py
   ```

The script will log its progress and create a `sync.db` file to record
which files have been uploaded.
