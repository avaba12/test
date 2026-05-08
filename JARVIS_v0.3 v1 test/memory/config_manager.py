"""Thread-sicherer Config-Manager mit JSON-basierten Einstellungen, Fallback und .env-Support."""
import json, threading, os
from pathlib import Path
from typing import Any, Optional

class ConfigManager:
    """Thread-sicherer Singleton Config-Manager.

    Phase 1 Fix:
    - API-Keys werden bevorzugt aus Umgebungsvariablen gelesen (.env)
    - JSON-Datei wird nicht mehr für Secrets empfohlen
    - get_api_key() prüft zuerst os.environ, dann api_keys.json
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self._file_lock = threading.RLock()
        base = Path(__file__).resolve().parent.parent
        self.settings_path = base / "config" / "settings.json"
        self.api_keys_path = base / "config" / "api_keys.json"
        self._cache = {}
        self._load()
        # Phase 1 Fix: Lade .env falls vorhanden
        try:
            from dotenv import load_dotenv
            env_path = base / ".env"
            if env_path.exists():
                load_dotenv(dotenv_path=env_path)
        except ImportError:
            pass

    def _load(self):
        try:
            with self._file_lock:
                if self.settings_path.exists():
                    self._cache = json.loads(self.settings_path.read_text(encoding="utf-8"))
                else:
                    self._cache = {}
        except Exception as e:
            print(f"[Config] ⚠️ Fallback nach Fehler: {e}")
            self._cache = {}

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        val = self._cache
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    def set(self, key: str, value: Any) -> None:
        with self._file_lock:
            keys = key.split(".")
            d = self._cache
            for k in keys[:-1]:
                if k not in d or not isinstance(d[k], dict):
                    d[k] = {}
                d = d[k]
            d[keys[-1]] = value
            self._save()

    def _save(self):
        try:
            self.settings_path.write_text(json.dumps(self._cache, indent=4, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print(f"[Config] ❌ Speichern fehlgeschlagen: {e}")

    def get_api_key(self, key: str) -> str:
        """Phase 1 Fix: Liest API-Key bevorzugt aus Umgebungsvariable.

        Reihenfolge:
        1. os.environ[key.upper()]  (z.B. GEMINI_API_KEY)
        2. os.environ[key]          (exakter Name)
        3. api_keys.json            (Fallback, veraltet)
        """
        # 1. Umgebungsvariable (empfohlen)
        env_val = os.environ.get(key.upper()) or os.environ.get(key)
        if env_val:
            return env_val.strip()
        # 2. JSON-Fallback (veraltet, nur für Migration)
        try:
            with self._file_lock:
                if self.api_keys_path.exists():
                    data = json.loads(self.api_keys_path.read_text(encoding="utf-8"))
                    return data.get(key, "")
        except Exception:
            pass
        return ""

    def set_api_key(self, key: str, value: str) -> None:
        """Phase 1 Fix: Speichert API-Key NICHT mehr in JSON.

        Stattdessen wird eine .env-Datei erstellt/aktualisiert.
        """
        try:
            base = Path(__file__).resolve().parent.parent
            env_path = base / ".env"

            # Lese bestehende .env
            lines = []
            if env_path.exists():
                lines = env_path.read_text(encoding="utf-8").splitlines()

            # Aktualisiere oder füge hinzu
            new_line = f"{key.upper()}={value}"
            updated = False
            for i, line in enumerate(lines):
                if line.startswith(f"{key.upper()}="):
                    lines[i] = new_line
                    updated = True
                    break
            if not updated:
                lines.append(new_line)

            env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            # Auch in os.environ setzen (sofort aktiv)
            os.environ[key.upper()] = value

            # Alte JSON-Datei bereinigen (Key entfernen)
            try:
                with self._file_lock:
                    if self.api_keys_path.exists():
                        data = json.loads(self.api_keys_path.read_text(encoding="utf-8"))
                        if key in data:
                            del data[key]
                            self.api_keys_path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass
        except Exception as e:
            print(f"[Config] ❌ API-Key speichern fehlgeschlagen: {e}")

    def reload(self):
        self._load()

    @property
    def all(self) -> dict:
        return dict(self._cache)
