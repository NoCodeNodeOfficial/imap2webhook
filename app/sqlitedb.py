import sqlite3
import logging

logger = logging.getLogger(__name__)

class SqliteDb:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self._init_table()
        self.email_uids = self._load_uids()

    def _init_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS email_uids (
                id  INTEGER PRIMARY KEY,
                uid INTEGER
            )
        """)
        self.conn.commit()

    def _load_uids(self):
        rows = self.conn.execute("SELECT uid FROM email_uids").fetchall()
        loaded_uids = {row[0] for row in rows}
        return loaded_uids

    def flush_uids(self):
        self.conn.execute("DELETE FROM email_uids")
        self.conn.commit()
        self.email_uids = set()

    def insert_uid(self, uid):
        self.conn.execute("INSERT INTO email_uids (uid) VALUES (?)", (uid,))
        self.conn.commit()
        self.email_uids.add(uid)