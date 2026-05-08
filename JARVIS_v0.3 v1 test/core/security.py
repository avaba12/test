"""Sicherheits-Modul: PIN, Session-Timeout, Rate-Limit, Input-Sanitization.

Phase 1 Fixes:
- PIN wird mit PBKDF2-HMAC-SHA256 + Salt gehasht (statt plain SHA256)
- Thread-sichere Session-Verwaltung
- Stärkere Input-Validierung
"""
import time, re, hashlib, secrets, threading
from typing import Optional, Dict
from memory.config_manager import ConfigManager
from memory.memory_manager import MemoryManager

class SecurityManager:
    def __init__(self):
        self.cfg = ConfigManager()
        self.memory = MemoryManager()
        self._sessions: Dict[str, float] = {}
        self._rate_limit: Dict[str, list] = {}
        self._pin_verified = False
        self._last_activity = time.time()
        self._session_lock = threading.Lock()

    def _hash_pin(self, pin: str, salt: Optional[str] = None) -> str:
        """Phase 1 Fix: PBKDF2-HMAC-SHA256 mit Salt (100.000 Iterationen)."""
        if salt is None:
            salt = secrets.token_hex(16)
        hashed = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt.encode("utf-8"), 100000)
        return f"{salt}${hashed.hex()}"

    def _verify_pin(self, pin: str, stored: str) -> bool:
        """Verifiziert PIN gegen gespeicherten Hash."""
        if "$" not in stored:
            # Legacy: alter SHA256-Hash → Migration
            return False
        salt, _ = stored.split("$", 1)
        return self._hash_pin(pin, salt) == stored

    def check_pin(self, pin: str) -> bool:
        stored = self.cfg.get("pin_code", "")
        if not stored or not self.cfg.get("pin_enabled", False):
            return True
        if self._verify_pin(pin, stored):
            with self._session_lock:
                self._pin_verified = True
                self._last_activity = time.time()
            self.memory.audit("pin_success", "PIN erfolgreich eingegeben", "user")
            return True
        self.memory.audit("pin_fail", "Falsche PIN eingegeben", "user")
        return False

    def set_pin(self, pin: str) -> None:
        """Phase 1 Fix: Setzt PIN mit PBKDF2 + Salt."""
        if not pin or len(pin) < 4:
            raise ValueError("PIN muss mindestens 4 Zeichen haben")
        if not pin.isdigit():
            raise ValueError("PIN darf nur Zahlen enthalten")
        hashed = self._hash_pin(pin)
        self.cfg.set("pin_code", hashed)
        self.cfg.set("pin_enabled", True)
        self.memory.audit("pin_set", "PIN wurde neu gesetzt (PBKDF2)", "user")

    def is_session_valid(self) -> bool:
        timeout = self.cfg.get("session_timeout", 30) * 60
        with self._session_lock:
            if time.time() - self._last_activity > timeout:
                self._pin_verified = False
                return False
            return True

    def touch(self):
        with self._session_lock:
            self._last_activity = time.time()

    def check_rate_limit(self, ip: str = "local", max_req: int = 60, window: int = 60) -> bool:
        now = time.time()
        if ip not in self._rate_limit:
            self._rate_limit[ip] = []
        self._rate_limit[ip] = [t for t in self._rate_limit[ip] if now - t < window]
        if len(self._rate_limit[ip]) >= max_req:
            return False
        self._rate_limit[ip].append(now)
        return True

    @staticmethod
    def sanitize_app_name(name: str) -> str:
        """Phase 1 Fix: Strengere Sanitization für App-Namen."""
        sanitized = re.sub(r"[^a-zA-Z0-9\s\.\-\_]", "", name).strip()
        # Verhindere Pfad-Traversal
        if ".." in sanitized or "/" in sanitized or "\\" in sanitized:
            raise ValueError("Ungültiger App-Name: Pfad-Traversal erkannt")
        return sanitized

    @staticmethod
    def sanitize_url(url: str) -> Optional[str]:
        """Phase 1 Fix: Strengere URL-Validierung."""
        url = url.strip()
        if not url:
            return None
        # Erlaubte Protokolle
        if not url.startswith(("http://", "https://")):
            return None
        # Blockiere gefährliche Protokolle und Patterns
        dangerous = ["file://", "ftp://", "dict://", "gopher://", "ldap://", "javascript:", "data:"]
        if any(url.lower().startswith(d) for d in dangerous):
            return None
        # Blockiere Localhost/Internal IPs (optional, je nach Use-Case)
        blocked_hosts = ["localhost", "127.0.0.1", "0.0.0.0", "::1", "192.168.", "10.", "172.16."]
        lower = url.lower()
        for bh in blocked_hosts:
            if bh in lower:
                return None
        return url

    @staticmethod
    def is_dangerous_command(text: str) -> bool:
        """Phase 1 Fix: Erweiterte Liste gefährlicher Shell-Operatoren."""
        dangerous = [";", "|", "&&", "||", "`", "$()", ">>", "<(", "&", "#", "\n", "\x00"]
        return any(d in text for d in dangerous)

    def require_confirmation(self, action: str) -> bool:
        if not self.cfg.get("confirmation_required", True):
            return False
        dangerous_actions = [
            "delete", "remove", "uninstall", "shutdown", "restart", "format", "rm -rf",
            "del ", "rmdir", "erase", "deltree", "mkfs", "dd if=", "format ", "reg delete"
        ]
        needs_confirm = any(d in action.lower() for d in dangerous_actions)
        if needs_confirm:
            self.memory.audit("confirmation_required", f"Bestaetigung angefordert fuer: {action[:100]}", "system")
        return needs_confirm
