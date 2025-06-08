"""Moodle to Google Drive Auto-Sync Tool.

This script logs into a Moodle instance, checks for newly uploaded files
for each enrolled course and uploads them to a folder structure in
Google Drive. A local SQLite database is used to track already synced
files so subsequent runs only transfer new content.
"""
from __future__ import annotations

import os
import sqlite3
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterable, List

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

DB_PATH = os.getenv("SYNC_DB", "sync.db")


@contextmanager
def db_connection(path: str = DB_PATH):
    conn = sqlite3.connect(path)
    yield conn
    conn.commit()
    conn.close()


def init_db(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS synced_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_url TEXT UNIQUE,
            file_name TEXT,
            course TEXT,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()


def file_already_synced(conn: sqlite3.Connection, file_url: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM synced_files WHERE file_url=?", (file_url,))
    return cur.fetchone() is not None


def record_file(conn: sqlite3.Connection, file_url: str, file_name: str, course: str) -> None:
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO synced_files (file_url, file_name, course) VALUES (?, ?, ?)",
        (file_url, file_name, course),
    )
    conn.commit()


def authenticate_drive():
    creds_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    if not creds_file:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_FILE env var not set")

    creds = Credentials.from_service_account_file(
        creds_file, scopes=["https://www.googleapis.com/auth/drive"]
    )
    service = build("drive", "v3", credentials=creds)
    return service


def ensure_folder(service, parent_id: str, name: str) -> str:
    query = (
        f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' "
        f"and name='{name}' and trashed=false"
    )
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]

    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    created = service.files().create(body=metadata, fields="id").execute()
    return created["id"]


def upload_file(service, parent_id: str, path: str) -> None:
    metadata = {"name": os.path.basename(path), "parents": [parent_id]}
    media = MediaFileUpload(path, resumable=True)
    service.files().create(body=metadata, media_body=media, fields="id").execute()
    logging.info("Uploaded %s", os.path.basename(path))


@dataclass
class MoodleFile:
    name: str
    url: str
    course: str


class MoodleScraper:
    """Minimal scraper for a Moodle instance using selenium."""

    def __init__(self, base_url: str, headless: bool = True):
        opts = Options()
        if headless:
            opts.add_argument("--headless=new")
        self.driver = webdriver.Chrome(options=opts)
        self.base_url = base_url

    def login(self, username: str, password: str) -> None:
        self.driver.get(self.base_url)
        # The actual selectors depend on the Moodle theme; adjust as needed.
        self.driver.find_element(By.ID, "username").send_keys(username)
        self.driver.find_element(By.ID, "password").send_keys(password)
        self.driver.find_element(By.ID, "loginbtn").click()

    def list_courses(self) -> List[str]:
        # This method should return URLs for each course a user is enrolled in.
        # Implementation will depend on the Moodle layout.
        courses: List[str] = []
        for link in self.driver.find_elements(By.CSS_SELECTOR, "a.course-link"):
            url = link.get_attribute("href")
            courses.append(url)
        return courses

    def scrape_course_files(self, course_url: str) -> Iterable[MoodleFile]:
        self.driver.get(course_url)
        course_name = self.driver.find_element(By.CSS_SELECTOR, "h1").text
        elements = self.driver.find_elements(By.CSS_SELECTOR, "a.resource")
        for el in elements:
            file_url = el.get_attribute("href")
            filename = el.text.strip()
            yield MoodleFile(name=filename, url=file_url, course=course_name)

    def close(self) -> None:
        self.driver.quit()


def main() -> None:
    username = os.getenv("MOODLE_USERNAME")
    password = os.getenv("MOODLE_PASSWORD")
    moodle_url = os.getenv("MOODLE_LOGIN_URL")
    drive_root = os.getenv("DRIVE_ROOT", "Moodle Sync")

    if not all([username, password, moodle_url]):
        raise RuntimeError("Missing Moodle configuration in environment variables")

    with db_connection() as conn:
        init_db(conn)
        service = authenticate_drive()
        scraper = MoodleScraper(moodle_url)
        scraper.login(username, password)

        root_results = service.files().list(q=f"name='{drive_root}' and mimeType='application/vnd.google-apps.folder' and trashed=false", fields="files(id)").execute()
        if root_results.get("files"):
            root_id = root_results["files"][0]["id"]
        else:
            root_id = service.files().create(body={"name": drive_root, "mimeType": "application/vnd.google-apps.folder"}, fields="id").execute()["id"]

        for course_url in scraper.list_courses():
            for mfile in scraper.scrape_course_files(course_url):
                if file_already_synced(conn, mfile.url):
                    continue
                course_id = ensure_folder(service, root_id, mfile.course)
                local_dir = os.path.join("tmp", mfile.course)
                os.makedirs(local_dir, exist_ok=True)
                local_path = os.path.join(local_dir, mfile.name)
                scraper.driver.get(mfile.url)
                with open(local_path, "wb") as f:
                    f.write(scraper.driver.find_element(By.TAG_NAME, "body").screenshot_as_png)
                upload_file(service, course_id, local_path)
                record_file(conn, mfile.url, mfile.name, mfile.course)
                os.remove(local_path)
        scraper.close()
    logging.info("Sync complete")


if __name__ == "__main__":
    main()
