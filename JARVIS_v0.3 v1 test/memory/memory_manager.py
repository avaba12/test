"""SQLite Memory-Manager mit Write-Queue, Connection-Pooling, Auto-Cleanup und Backup.

Phase 4 Fixes:
- Connection-Pooling (wiederverwendet Connections)
- Thread-sicheres Connection-Management
- Automatisches SQLite-Backup
"""
import sqlite3, threading, json, time, os, shutil
from pathlib import Path
from typing import List, Dict, Optional

class MemoryManager:
    def __init__(self, db_path: Optional[Path] = None):
        base = Path(__file__).resolve().parent.parent
        self.db_path = db_path or (base / "data" / "memory.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._queue = []
        self._queue_lock = threading.Lock()
        self._conn = None
        self._init_db()
        self._start_writer()

    def _get_conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        return self._conn

    def _init_db(self):
        with self._lock:
            conn = self._get_conn()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp REAL, role TEXT,
                    content TEXT, model TEXT, session_id TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp REAL,
                    action TEXT, details TEXT, user TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_time ON conversations(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON conversations(session_id)")
            conn.commit()

    def _start_writer(self):
        def writer():
            while True:
                time.sleep(1.0)
                self._flush_queue()
        t = threading.Thread(target=writer, daemon=True, name="MemoryWriter")
        t.start()

    def _flush_queue(self):
        with self._queue_lock:
            if not self._queue: return
            batch = self._queue[:]
            self._queue.clear()
        try:
            with self._lock:
                conn = self._get_conn()
                for item in batch:
                    conn.execute(
                        "INSERT INTO conversations (timestamp, role, content, model, session_id) VALUES (?,?,?,?,?)",
                        (item["time"], item["role"], item["content"], item.get("model", ""), item.get("session", "default"))
                    )
                conn.commit()
        except Exception as e:
            print(f"[Memory] Flush error: {e}")

    def add(self, role: str, content: str, model: str = "", session: str = "default"):
        with self._queue_lock:
            self._queue.append({"time": time.time(), "role": role, "content": content, "model": model, "session": session})
        self._maybe_cleanup()

    def get_history(self, limit: int = 100, session: str = "default") -> List[Dict]:
        self._flush_queue()
        try:
            with self._lock:
                conn = self._get_conn()
                cur = conn.execute(
                    "SELECT timestamp, role, content, model FROM conversations WHERE session_id=? ORDER BY timestamp DESC LIMIT ?",
                    (session, limit)
                )
                rows = cur.fetchall()
                return [{"time": r[0], "role": r[1], "content": r[2], "model": r[3]} for r in reversed(rows)]
        except Exception as e:
            print(f"[Memory] Get history error: {e}")
            return []

    def audit(self, action: str, details: str = "", user: str = "system"):
        try:
            with self._lock:
                conn = self._get_conn()
                conn.execute("INSERT INTO audit_log (timestamp, action, details, user) VALUES (?,?,?,?)",
                    (time.time(), action, details, user))
                conn.commit()
        except Exception as e:
            print(f"[Memory] Audit error: {e}")

    def get_stats(self) -> Dict:
        self._flush_queue()
        try:
            with self._lock:
                conn = self._get_conn()
                total = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
                size = os.path.getsize(self.db_path)
                return {"entries": total, "size_mb": round(size / 1024 / 1024, 2)}
        except Exception:
            return {"entries": 0, "size_mb": 0}

    def cleanup(self, keep: int = 1000):
        self._flush_queue()
        try:
            with self._lock:
                conn = self._get_conn()
                total_before = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
                conn.execute("DELETE FROM conversations WHERE id NOT IN (SELECT id FROM conversations ORDER BY timestamp DESC LIMIT ?)", (keep,))
                total_after = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
                deleted = total_before - total_after
                conn.execute("VACUUM")
                conn.commit()
                print(f"[Memory] Cleanup: {deleted} Eintraege entfernt")
                return deleted
        except Exception as e:
            print(f"[Memory] Cleanup error: {e}")
            return 0

    def _maybe_cleanup(self):
        from memory.config_manager import ConfigManager
        cfg = ConfigManager()
        limit = cfg.get("memory_limit", 1000)
        if limit <= 0: return
        stats = self.get_stats()
        if stats["entries"] > limit * 1.2:
            self.cleanup(keep=limit)

    def export_json(self, path: Path) -> bool:
        self._flush_queue()
        try:
            with self._lock:
                conn = self._get_conn()
                cur = conn.execute("SELECT timestamp, role, content, model, session_id FROM conversations ORDER BY timestamp")
                rows = cur.fetchall()
                data = [{"time": r[0], "role": r[1], "content": r[2], "model": r[3], "session": r[4]} for r in rows]
                path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                return True
        except Exception as e:
            print(f"[Memory] Export error: {e}")
            return False

    def backup(self) -> bool:
        try:
            backup_dir = self.db_path.parent / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"memory_backup_{ts}.db"
            shutil.copy2(self.db_path, backup_path)
            backups = sorted(backup_dir.glob("memory_backup_*.db"))
            for old in backups[:-7]:
                old.unlink(missing_ok=True)
            return True
        except Exception as e:
            print(f"[Memory] Backup error: {e}")
            return False
