import os
import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict


def init_db(app_dir: str) -> bool:
    """Initialize the database, including creating necessary tables if they don't exist."""
    db_path = os.path.join(app_dir, "whitelist.db")
    try:
        with sqlite3.connect(db_path) as conn:
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

        logging.info(f"[db] Database initialized successfully at {db_path}")
        return True
    except Exception as e:
        logging.error(f"[db] Failed to initialize database: {str(e)}")
        return False


def _db_path(app_dir: str) -> str:
    return os.path.join(app_dir, "whitelist.db")


def upsert_regions(app_dir: str,
                   conn: sqlite3.Connection,
                   regions: List[Dict], cloud_provider: str = 'aliyun',
                   ) -> None:
    try:
        logging.info(f"[db] Upserting {len(regions)} regions into database for cloud provider: {cloud_provider}")
        cursor = conn.cursor()
        for region in regions:
            region_id = region.get('RegionId', '')
            if not region_id:
                continue
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                """
                INSERT INTO regions (region_id, name, region_endpoint, cloud_provider, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(region_id) DO UPDATE SET
                    name=excluded.name,
                    region_endpoint=excluded.region_endpoint,
                    cloud_provider=excluded.cloud_provider,
                    updated_at=excluded.updated_at
                """,
                (region_id, region.get('LocalName', ''), region.get('RegionEndpoint', ''), cloud_provider, now_iso, now_iso)
            )
        conn.commit()
    except Exception as e:
        logging.error(f"[db] Failed to upsert regions: {e}")


def load_cached_regions(app_dir: str, conn: sqlite3.Connection) -> List[Dict]:

    try:
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
    except Exception as e:
        logging.error(f"[db] Failed to load cached regions: {e}")
        return []


def is_cache_fresh(conn: sqlite3.Connection, max_age_days: int = 1) -> bool:

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT date(MAX(updated_at)) FROM regions")
        row = cursor.fetchone()
    except Exception as e:
        logging.error(f"[db] Failed to check cache freshness: {e}")
        return False

    if not row or not row[0]:
        return False

    try:
        # 可能存储的字符串是日期 (YYYY-MM-DD) 或含时区的日期时间

        normalized = row[0].replace("Z", "+00:00")
        last_dt = datetime.fromisoformat(normalized)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        last_date = last_dt.astimezone().date()

    except Exception:
        return False

    local_today = datetime.now(timezone.utc).astimezone().date()
    if max_age_days < 0:
        return False

    logging.info("last_date=%s local_today=%s max_age_days=%s", last_date, local_today, max_age_days)

    return last_date > (local_today - timedelta(days=max_age_days))
