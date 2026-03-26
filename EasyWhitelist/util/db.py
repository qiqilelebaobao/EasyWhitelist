import os
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Dict


def init_db(app_dir: str) -> bool:
    """Initialize the database, including creating necessary tables if they don't exist."""
    try:
        db_path = os.path.join(app_dir, "whitelist.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create regions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS regions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                region_id TEXT UNIQUE NOT NULL,
                name TEXT,
                region_endpoint TEXT,
                cloud_provider TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')

        # Create templates table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                region TEXT NOT NULL,
                prefix_list_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')

        # Create rules table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (template_id) REFERENCES templates (id) ON DELETE CASCADE
            )
        ''')

        conn.commit()
        logging.info(f"[db] Database initialized successfully at {db_path}")
        return True
    except Exception as e:
        logging.error(f"[db] Failed to initialize database: {str(e)}")
        return False


def _db_path(app_dir: str) -> str:
    return os.path.join(app_dir, "whitelist.db")


def upsert_regions(app_dir: str, regions: List[Dict], cloud_provider: str = 'aliyun') -> None:
    with sqlite3.connect(_db_path(app_dir)) as conn:
        cursor = conn.cursor()
        for region in regions:
            region_id = region.get('RegionId', '')
            if not region_id:
                continue
            cursor.execute(
                """
                INSERT INTO regions (region_id, name, region_endpoint, cloud_provider, created_at, updated_at)
                VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
                ON CONFLICT(region_id) DO UPDATE SET
                    name=excluded.name,
                    region_endpoint=excluded.region_endpoint,
                    cloud_provider=excluded.cloud_provider,
                    updated_at=datetime('now')
                """,
                (region_id, region.get('LocalName', ''), region.get('RegionEndpoint', ''), cloud_provider)
            )


def load_cached_regions(app_dir: str) -> List[Dict]:
    with sqlite3.connect(_db_path(app_dir)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT region_id, name, region_endpoint, cloud_provider FROM regions")
        rows = cursor.fetchall()

    return [
        {
            'RegionId': r[0],
            'LocalName': r[1],
            'RegionEndpoint': r[2],
            'CloudProvider': r[3],
        }
        for r in rows
    ]


def is_cache_fresh(app_dir: str, max_age_days: int = 1) -> bool:
    with sqlite3.connect(_db_path(app_dir)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT date(MAX(updated_at)) FROM regions")
        row = cursor.fetchone()

    if not row or not row[0]:
        return False

    try:
        last_date = datetime.fromisoformat(row[0]).date()
    except ValueError:
        return False

    today = datetime.utcnow().date()
    if max_age_days < 0:
        return False

    return last_date >= (today - timedelta(days=max_age_days))
