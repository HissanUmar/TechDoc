"""SQLite-backed state store for persistent, versioned state management."""

import sqlite3
import json
import os
from threading import RLock
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path


class DatabaseStateStore:
    """
    Persistent state store using SQLite.
    
    Implements the same interface as InMemoryStateStore but persists all state
    changes to a local SQLite database. Ensures durability across Colab session
    restarts and provides a full audit trail of all state mutations.
    """

    def __init__(self, db_path: str = "/tmp/agentic_framework_state.db"):
        """
        Initialize the database state store.
        
        Args:
            db_path: Path to SQLite database file (default: /tmp/agentic_framework_state.db)
        """
        self.db_path = db_path
        self._lock = RLock()
        self._version_counter = 0
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database schema if not already done."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create state table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS state (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    version INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create history table for audit trail
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT,
                    value TEXT,
                    operation TEXT,
                    version INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create snapshots table for restore capability
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_data TEXT,
                    version INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
            conn.close()
            
            # Load max version from history
            self._load_max_version()

    def _load_max_version(self) -> None:
        """Load the maximum version from the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(version) FROM history")
        max_version = cursor.fetchone()[0]
        conn.close()
        self._version_counter = max_version if max_version else 0

    def set(self, key: str, value: Any) -> int:
        """
        Set a key-value pair and persist to database.
        
        Args:
            key: State key
            value: Value to store (must be JSON-serializable)
        
        Returns:
            New version number
        """
        with self._lock:
            self._version_counter += 1
            version = self._version_counter
            
            # Serialize value to JSON
            try:
                json_value = json.dumps(value)
            except TypeError:
                json_value = json.dumps(str(value))
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Insert or update state
            cursor.execute("""
                INSERT OR REPLACE INTO state (key, value, version)
                VALUES (?, ?, ?)
            """, (key, json_value, version))
            
            # Log to history
            cursor.execute("""
                INSERT INTO history (key, value, operation, version)
                VALUES (?, ?, ?, ?)
            """, (key, json_value, "set", version))
            
            conn.commit()
            conn.close()
            
            return version

    def get(self, key: str) -> Any:
        """
        Retrieve a value by key from the database.
        
        Args:
            key: State key
        
        Returns:
            Value associated with key, or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM state WHERE key = ?", (key,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                try:
                    return json.loads(result[0])
                except json.JSONDecodeError:
                    return result[0]
            return None

    def cas(self, key: str, expected: Any, new_value: Any) -> bool:
        """
        Compare-and-swap: only set if current value matches expected.
        
        Args:
            key: State key
            expected: Expected current value
            new_value: New value to set if comparison succeeds
        
        Returns:
            True if swap succeeded, False if current value didn't match
        """
        with self._lock:
            current = self.get(key)
            if current == expected:
                self.set(key, new_value)
                return True
            return False

    def snapshot(self) -> Tuple[int, Dict[str, Any]]:
        """
        Create a snapshot of current state.
        
        Returns:
            Tuple of (version, state_dict)
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM state")
            rows = cursor.fetchall()
            conn.close()
            
            state_dict = {}
            for key, json_value in rows:
                try:
                    state_dict[key] = json.loads(json_value)
                except json.JSONDecodeError:
                    state_dict[key] = json_value
            
            # Save snapshot
            snapshot_data = json.dumps(state_dict)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO snapshots (snapshot_data, version)
                VALUES (?, ?)
            """, (snapshot_data, self._version_counter))
            conn.commit()
            conn.close()
            
            return (self._version_counter, state_dict)

    def restore(self, version: int) -> bool:
        """
        Restore state to a previous version from history.
        
        Args:
            version: Version number to restore to
        
        Returns:
            True if restore succeeded, False if version not found
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get all state entries at or before the specified version
            cursor.execute("""
                SELECT key, value FROM (
                    SELECT key, value, MAX(version) as v
                    FROM history
                    WHERE version <= ?
                    GROUP BY key
                )
                WHERE v <= ?
            """, (version, version))
            
            rows = cursor.fetchall()
            
            if not rows:
                conn.close()
                return False
            
            # Clear current state
            cursor.execute("DELETE FROM state")
            
            # Restore state
            for key, json_value in rows:
                cursor.execute("""
                    INSERT INTO state (key, value, version)
                    VALUES (?, ?, ?)
                """, (key, json_value, version))
            
            conn.commit()
            conn.close()
            
            self._version_counter = version
            return True

    def history(self) -> List[Tuple[int, str, str]]:
        """
        Get the full audit trail of state changes.
        
        Returns:
            List of (version, key, operation) tuples
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT version, key, operation
                FROM history
                ORDER BY id ASC
            """)
            rows = cursor.fetchall()
            conn.close()
            return rows

    def keys(self) -> List[str]:
        """
        Get all current state keys.
        
        Returns:
            List of all keys in current state
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT key FROM state")
            rows = cursor.fetchall()
            conn.close()
            return [row[0] for row in rows]

    def clear(self) -> None:
        """Clear all state from the database."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM state")
            cursor.execute("DELETE FROM history")
            cursor.execute("DELETE FROM snapshots")
            conn.commit()
            conn.close()
            self._version_counter = 0

    def get_status(self) -> Dict[str, Any]:
        """
        Get database status information.
        
        Returns:
            Dictionary with database stats
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM state")
            state_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM history")
            history_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM snapshots")
            snapshot_count = cursor.fetchone()[0]
            
            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            
            conn.close()
            
            return {
                "type": "DatabaseStateStore",
                "db_path": self.db_path,
                "db_size_bytes": db_size,
                "current_version": self._version_counter,
                "state_entries": state_count,
                "history_entries": history_count,
                "snapshots": snapshot_count,
            }
