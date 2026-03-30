import os
import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional


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
                    cloud_provider TEXT NOT NULL,
                    region_id TEXT UNIQUE NOT NULL,
                    name TEXT,
                    region_endpoint TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            ''')

            # Create security group cache table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS security_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cloud_provider TEXT NOT NULL,
                    sg_id TEXT UNIQUE NOT NULL,
                    region_id TEXT NOT NULL,
                    sg_name TEXT,
                    vpc_id TEXT,
                    sg_type TEXT,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            ''')

            # Create IP address history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ip_addresses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    raw_ip TEXT,
                    normalized_cidr TEXT NOT NULL,
                    resv1 TEXT,
                    resv2 TEXT,
                    resv3 TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(raw_ip)
                )
            ''')

        logging.debug("[db] Database initialized successfully at %s", db_path)
        return True
    except Exception as e:
        logging.error("[db] Failed to initialize database: %s", e)
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
        logging.error("[db] Failed to upsert regions: %s", e)
        conn.rollback()


def upsert_security_group(conn: sqlite3.Connection,
                          sg_id: str,
                          cloud_provider: str,
                          region_id: str,
                          sg_name: str = '',
                          vpc_id: str = '',
                          sg_type: str = '',
                          description: str = '') -> None:
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO security_groups (sg_id, region_id, sg_name, vpc_id, sg_type, description, cloud_provider, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sg_id) DO UPDATE SET
                region_id=excluded.region_id,
                sg_name=excluded.sg_name,
                vpc_id=excluded.vpc_id,
                sg_type=excluded.sg_type,
                description=excluded.description,
                cloud_provider=excluded.cloud_provider,
                updated_at=excluded.updated_at
            """,
            (sg_id, region_id, sg_name, vpc_id, sg_type, description, cloud_provider, now_iso, now_iso)
        )
        conn.commit()
    except Exception as e:
        logging.error("[db] Failed to upsert security group: %s", e)
        conn.rollback()


def refresh_security_group_update_time(conn: sqlite3.Connection, sg_id: str) -> None:
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE security_groups
            SET updated_at = ?
            WHERE sg_id = ?
            """,
            (now_iso, sg_id)
        )
        conn.commit()
    except Exception as e:
        logging.error("[db] Failed to update security group updated_at: %s", e)
        conn.rollback()


def upsert_ip_address(conn: sqlite3.Connection,
                      raw_ip: Optional[str],
                      normalized_cidr: str) -> None:
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO ip_addresses (raw_ip, normalized_cidr, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(raw_ip) DO UPDATE SET
                normalized_cidr=excluded.normalized_cidr,
                updated_at=excluded.updated_at
            """,
            (raw_ip, normalized_cidr, now_iso, now_iso)
        )
        conn.commit()
    except Exception as e:
        logging.error("[db] Failed to upsert ip address: %s", e)
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
        logging.error("[db] Failed to load cached regions: %s", e)
        return []


def load_cached_security_group(conn: sqlite3.Connection, sg_id: str) -> Dict[str, str]:
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT sg_id, region_id, sg_name, vpc_id, sg_type, description, cloud_provider FROM security_groups WHERE sg_id = ?", (sg_id,))
        row = cursor.fetchone()
        if not row:
            return {}
        return {
            'sg_id': row[0],
            'region_id': row[1],
            'sg_name': row[2],
            'vpc_id': row[3],
            'sg_type': row[4],
            'description': row[5],
            'cloud_provider': row[6],
        }
    except Exception as e:
        logging.error("[db] Failed to load cached security group: %s", e)
        return {}


def is_cache_fresh(conn: sqlite3.Connection, max_age_days: int = 1) -> bool:
    if max_age_days < 0:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT MIN(updated_at) FROM regions")
        row = cursor.fetchone()
        logging.debug("[db] Cache freshness check - latest updated_at: %s", row[0] if row else "None")
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
        logging.warning("[db] Unparseable updated_at: %s", val)
        return False

    local_today = datetime.now(timezone.utc).astimezone().date()

    is_fresh = last_dt.astimezone().date() > (local_today - timedelta(days=max_age_days))
    logging.debug("[db] Cache freshness check - last updated_at: %s, local today: %s, max_age_days: %d, is_fresh: %s",
                  last_dt.isoformat(), local_today.isoformat(), max_age_days, is_fresh)

    return is_fresh
