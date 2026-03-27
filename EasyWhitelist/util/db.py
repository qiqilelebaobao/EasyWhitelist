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

            # Create security group cache table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS security_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sg_id TEXT UNIQUE NOT NULL,
                    region_id TEXT NOT NULL,
                    region_name TEXT,
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


def upsert_regions(conn: sqlite3.Connection,
                   regions: List[Dict], cloud_provider: str = 'aliyun',
                   ) -> None:
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        cursor = conn.cursor()
        for region in regions:
            region_id = region.get('RegionId', '')
            if not region_id:
                continue
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
                (region_id,
                 region.get('LocalName', ''),
                 region.get('RegionEndpoint', ''),
                 cloud_provider,
                 now_iso,
                 now_iso)
            )
        conn.commit()
    except Exception as e:
        logging.error(f"[db] Failed to upsert regions: {e}")
        conn.rollback()


def upsert_security_group(conn: sqlite3.Connection,
                          sg_id: str,
                          region_id: str,
                          region_name: str = '') -> None:
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO security_groups (sg_id, region_id, region_name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(sg_id) DO UPDATE SET
                region_id=excluded.region_id,
                region_name=excluded.region_name,
                updated_at=excluded.updated_at
            """,
            (sg_id, region_id, region_name, now_iso, now_iso)
        )
        conn.commit()
    except Exception as e:
        logging.error(f"[db] Failed to upsert security group: {e}")
        conn.rollback()


def load_cached_regions(conn: sqlite3.Connection) -> List[Dict]:

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


def load_cached_security_group(conn: sqlite3.Connection, sg_id: str) -> Dict[str, str]:
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT sg_id, region_id, region_name FROM security_groups WHERE sg_id = ?", (sg_id,))
        row = cursor.fetchone()
        if not row:
            return {}
        return {
            'sg_id': row[0],
            'region_id': row[1],
            'region_name': row[2],
        }
    except Exception as e:
        logging.error(f"[db] Failed to load cached security group: {e}")
        return {}


def is_cache_fresh(conn: sqlite3.Connection, max_age_days: int = 1) -> bool:
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(updated_at) FROM regions")
        row = cursor.fetchone()
    except Exception as e:
        logging.error("[db] Failed to check cache freshness: %s", e)
        return False

    if not row or not row[0]:
        return False

    val = row[0].strip()
    try:
        if val.endswith("Z"):
            val = val[:-1] + "+00:00"
        last_dt = datetime.fromisoformat(val)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
    except ValueError:
        logging.warning("[db] unparseable updated_at: %s", val)
        return False

    local_today = datetime.now(timezone.utc).astimezone().date()

    if max_age_days < 0:
        return False

    return last_dt.astimezone().date() > (local_today - timedelta(days=max_age_days))
