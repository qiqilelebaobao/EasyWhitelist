import os
import sqlite3
import logging


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
                created_at TEXT NOT NULL
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
