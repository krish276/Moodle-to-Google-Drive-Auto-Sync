# Moodle to Google Drive Auto-Sync

This project provides a Python script that logs into a Moodle instance,
detects newly uploaded course files and mirrors them to Google Drive.
Synced files are tracked using a local SQLite database so repeated runs
only upload new materials.

## Requirements

- Python 3.9+
- Google Chrome/Chromium and a matching ChromeDriver available in your `PATH`
- Google service account credentials with the Drive API enabled
- See `requirements.txt` for Python packages

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and fill in the required values or export
   the following environment variables:
   - `MOODLE_LOGIN_URL` – URL of the Moodle login page
   - `MOODLE_USERNAME` and `MOODLE_PASSWORD`
   - `GOOGLE_SERVICE_ACCOUNT_FILE` – path to a service account JSON file
   - `DRIVE_ROOT_ID` – ID of the Google Drive folder to store uploads
   - `SYNC_DB` – (optional) path to the local SQLite database
3. Run the sync script:
   ```bash
   python sync.py
   ```

The script will log its progress and create a `sync.db` file to record
which files have been uploaded.

## Google Drive Setup

The script authenticates using a **service account**. To create one:

1. Visit the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project and enable the **Drive API**.
3. Create a service account and download a JSON key file.
4. Create a folder in your Google Drive and share it with the service
   account's email address, giving it **Editor** access.
5. Copy the last part of that folder's URL, for example from
   `https://drive.google.com/drive/folders/\<ID\>`, and use it as the
   value of `DRIVE_ROOT_ID`.
