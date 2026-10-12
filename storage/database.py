"""
Database module for persistent storage
"""

import aiosqlite
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import json

from utils.logger import get_logger


class Database:
    """SQLite database for The Looker plugin"""
    
    DB_PATH = Path(__file__).parent.parent / "data" / "looker.db"
    
    def __init__(self):
        self.logger = get_logger()
        self.db_path = self.DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database tables"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT UNIQUE,
                    first_name TEXT,
                    last_name TEXT,
                    is_bot INTEGER,
                    is_premium INTEGER,
                    phone_number TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Activities table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    activity_type TEXT,
                    timestamp TIMESTAMP,
                    chat_id INTEGER,
                    message_id INTEGER,
                    data TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(user_id),
                    INDEX idx_user_timestamp (user_id, timestamp)
                )
            """)
            
            # Status history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS status_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    status TEXT,
                    probability REAL,
                    timestamp TIMESTAMP,
                    sources TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(user_id),
                    INDEX idx_user_timestamp (user_id, timestamp)
                )
            """)
            
            # Last seen table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS last_seen (
                    user_id INTEGER PRIMARY KEY,
                    last_seen TIMESTAMP,
                    is_online INTEGER,
                    platform TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                )
            """)
            
            # Notifications table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    notification_type TEXT,
                    message TEXT,
                    data TEXT,
                    timestamp TIMESTAMP,
                    read INTEGER DEFAULT 0,
                    FOREIGN KEY(user_id) REFERENCES users(user_id),
                    INDEX idx_user_timestamp (user_id, timestamp)
                )
            """)
            
            # Watch list table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS watch_list (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE,
                    username TEXT,
                    is_watching INTEGER DEFAULT 1,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                )
            """)
            
            conn.commit()
            conn.close()
            self.logger.info("Database initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing database: {e}")
    
    def add_user(self, user_id: int, username: str, first_name: str = "", 
                 last_name: str = "", is_bot: bool = False, is_premium: bool = False) -> bool:
        """Add or update user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO users 
                (user_id, username, first_name, last_name, is_bot, is_premium)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, username, first_name, last_name, int(is_bot), int(is_premium)))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Error adding user: {e}")
            return False
    
    def add_activity(self, user_id: int, activity_type: str, chat_id: Optional[int] = None,
                    message_id: Optional[int] = None, data: Optional[Dict] = None) -> bool:
        """Add activity record"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            data_json = json.dumps(data) if data else "{}"
            
            cursor.execute("""
                INSERT INTO activities (user_id, activity_type, timestamp, chat_id, message_id, data)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, activity_type, datetime.now(), chat_id, message_id, data_json))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Error adding activity: {e}")
            return False
    
    def get_activities(self, user_id: int, hours: int = 24, limit: int = 100) -> List[Dict]:
        """Get user activities"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            cursor.execute("""
                SELECT id, user_id, activity_type, timestamp, chat_id, message_id, data
                FROM activities
                WHERE user_id = ? AND timestamp > ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (user_id, cutoff_time, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    'id': row[0],
                    'user_id': row[1],
                    'activity_type': row[2],
                    'timestamp': row[3],
                    'chat_id': row[4],
                    'message_id': row[5],
                    'data': json.loads(row[6]) if row[6] else {}
                }
                for row in rows
            ]
        except Exception as e:
            self.logger.error(f"Error getting activities: {e}")
            return []
    
    def add_status_record(self, user_id: int, status: str, probability: float, sources: List[str]) -> bool:
        """Record status change"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            sources_json = json.dumps(sources)
            
            cursor.execute("""
                INSERT INTO status_history (user_id, status, probability, timestamp, sources)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, status, probability, datetime.now(), sources_json))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Error recording status: {e}")
            return False
    
    def update_last_seen(self, user_id: int, is_online: bool, platform: Optional[str] = None) -> bool:
        """Update last seen info"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO last_seen (user_id, last_seen, is_online, platform)
                VALUES (?, ?, ?, ?)
            """, (user_id, datetime.now(), int(is_online), platform))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Error updating last seen: {e}")
            return False
    
    def get_last_seen(self, user_id: int) -> Optional[Dict]:
        """Get last seen info"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT user_id, last_seen, is_online, platform
                FROM last_seen
                WHERE user_id = ?
            """, (user_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'user_id': row[0],
                    'last_seen': row[1],
                    'is_online': bool(row[2]),
                    'platform': row[3]
                }
            return None
        except Exception as e:
            self.logger.error(f"Error getting last seen: {e}")
            return None
    
    def add_notification(self, user_id: int, notification_type: str, message: str, data: Optional[Dict] = None) -> bool:
        """Add notification record"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            data_json = json.dumps(data) if data else "{}"
            
            cursor.execute("""
                INSERT INTO notifications (user_id, notification_type, message, data, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, notification_type, message, data_json, datetime.now()))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Error adding notification: {e}")
            return False
    
    def get_notifications(self, user_id: int, hours: int = 24, unread_only: bool = False) -> List[Dict]:
        """Get notifications"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            query = """
                SELECT id, user_id, notification_type, message, data, timestamp, read
                FROM notifications
                WHERE user_id = ? AND timestamp > ?
            """
            
            if unread_only:
                query += " AND read = 0"
            
            query += " ORDER BY timestamp DESC"
            
            cursor.execute(query, (user_id, cutoff_time))
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    'id': row[0],
                    'user_id': row[1],
                    'notification_type': row[2],
                    'message': row[3],
                    'data': json.loads(row[4]) if row[4] else {},
                    'timestamp': row[5],
                    'read': bool(row[6])
                }
                for row in rows
            ]
        except Exception as e:
            self.logger.error(f"Error getting notifications: {e}")
            return []
    
    def add_to_watch_list(self, user_id: int, username: str) -> bool:
        """Add user to watch list"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO watch_list (user_id, username, is_watching)
                VALUES (?, ?, 1)
            """, (user_id, username))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Error adding to watch list: {e}")
            return False
    
    def remove_from_watch_list(self, user_id: int) -> bool:
        """Remove user from watch list"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE watch_list SET is_watching = 0 WHERE user_id = ?
            """, (user_id,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Error removing from watch list: {e}")
            return False
    
    def get_watch_list(self) -> List[Dict]:
        """Get all watched users"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT user_id, username, added_at
                FROM watch_list
                WHERE is_watching = 1
            """)
            
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    'user_id': row[0],
                    'username': row[1],
                    'added_at': row[2]
                }
                for row in rows
            ]
        except Exception as e:
            self.logger.error(f"Error getting watch list: {e}")
            return []
    
    def cleanup_old_data(self, days: int = 30) -> int:
        """Clean up old data"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_time = datetime.now() - timedelta(days=days)
            
            # Delete old activities
            cursor.execute("""
                DELETE FROM activities WHERE timestamp < ?
            """, (cutoff_time,))
            
            # Delete old status history
            cursor.execute("""
                DELETE FROM status_history WHERE timestamp < ?
            """, (cutoff_time,))
            
            # Delete old notifications
            cursor.execute("""
                DELETE FROM notifications WHERE timestamp < ?
            """, (cutoff_time,))
            
            conn.commit()
            deleted = cursor.total_changes
            conn.close()
            
            self.logger.info(f"Cleaned up {deleted} old records")
            return deleted
        except Exception as e:
            self.logger.error(f"Error cleaning up database: {e}")
            return 0
