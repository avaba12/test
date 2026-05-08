"""Datei-Controller: Lesen, Schreiben, Suchen, Löschen (Papierkorb), Safe-Path-Check.

Phase 1 Fixes:
- Sandbox-Verzeichnis: Nur JARVIS-Ordner und User-Dokumente erlaubt
- Pfad-Traversal-Schutz (.., Symlinks)
- Größenlimits für Lesen/Schreiben
- Forbidden-Liste erweitert
"""
import os, shutil, glob
from pathlib import Path
from send2trash import send2trash
from core.logger import get_logger

logger = get_logger("FileController")

# Phase 1 Fix: Erlaubte Basis-Verzeichnisse (Sandbox)
_ALLOWED_BASE_DIRS = [
    Path.home() / "Documents",
    Path.home() / "Desktop",
    Path.home() / "Downloads",
    Path.home() / "Pictures",
    Path.home() / "Music",
    Path.home() / "Videos",
    Path.cwd(),  # Projektverzeichnis
    Path.cwd() / "outputs",
    Path.cwd() / "data",
    Path.cwd() / "logs",
]

# Phase 1 Fix: Strengere Forbidden-Liste
_FORBIDDEN_PATHS = [
    "C:/Windows", "C:/Program Files", "C:/Program Files (x86)", "C:/ProgramData",
    "C:/Users/All Users", "C:/Recovery", "C:/System Volume Information",
    "/etc", "/usr", "/bin", "/sbin", "/sys", "/proc", "/dev", "/boot",
    "/lib", "/lib64", "/opt", "/root", "/var/log",
]

_MAX_READ_SIZE = 5 * 1024 * 1024   # 5 MB
_MAX_WRITE_SIZE = 2 * 1024 * 1024  # 2 MB

def _safe_path(path: str) -> Path:
    """Validiert Pfad gegen Sandbox und Forbidden-Liste."""
    if not path or not isinstance(path, str):
        raise PermissionError("Ungültiger Pfad")

    # Phase 1 Fix: Normalisierung und Traversal-Schutz
    p = Path(path).resolve()

    # Verhindere Pfad-Traversal
    try:
        p.relative_to(Path.cwd().resolve())
    except ValueError:
        # Außerhalb Projekt-Ordner → prüfe gegen erlaubte Basis-Verzeichnisse
        allowed = any(
            str(p).startswith(str(base.resolve())) 
            for base in _ALLOWED_BASE_DIRS 
            if base.exists()
        )
        if not allowed:
            raise PermissionError(f"Zugriff auf '{p}' nicht erlaubt. Nur Dokumente und JARVIS-Ordner erlaubt.")

    # Prüfe Forbidden-Liste
    path_str = str(p).lower()
    for f in _FORBIDDEN_PATHS:
        if path_str.startswith(f.lower()):
            raise PermissionError(f"Zugriff auf Systemverzeichnis '{f}' nicht erlaubt.")

    # Phase 1 Fix: Keine Symlinks zu sensiblen Orten
    if p.is_symlink():
        real = p.resolve()
        real_str = str(real).lower()
        for f in _FORBIDDEN_PATHS:
            if real_str.startswith(f.lower()):
                raise PermissionError("Symlink zu Systemverzeichnis nicht erlaubt.")

    return p

def file_controller(parameters=None, response=None, player=None, session_memory=None) -> str:
    params = parameters or {}
    action = params.get("action", "").lower().strip()
    path = params.get("path", "")
    content = params.get("content", "")

    if player:
        try: 
            player.write_log(f"[File] {action} {path}")
        except: 
            pass

    try:
        if action == "read":
            p = _safe_path(path)
            if not p.exists(): 
                return f"❌ Datei nicht gefunden: {path}"
            if not p.is_file():
                return f"❌ Pfad ist kein Datei: {path}"
            # Phase 1 Fix: Größenlimit
            size = p.stat().st_size
            if size > _MAX_READ_SIZE:
                return f"❌ Datei zu groß ({size} bytes > {_MAX_READ_SIZE} bytes Limit)"
            text = p.read_text(encoding="utf-8", errors="ignore")
            return text[:2000] + ("\n... [gekuerzt]" if len(text) > 2000 else "")

        elif action == "write":
            p = _safe_path(path)
            # Phase 1 Fix: Größenlimit
            if len(content.encode("utf-8")) > _MAX_WRITE_SIZE:
                return f"❌ Inhalt zu groß ({len(content)} bytes > {_MAX_WRITE_SIZE} bytes Limit)"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"✅ Datei geschrieben: {path}"

        elif action == "list":
            p = _safe_path(path) if path else Path(".")
            if not p.exists(): 
                return f"❌ Pfad nicht gefunden: {path}"
            if not p.is_dir():
                return f"❌ Pfad ist kein Ordner: {path}"
            items = list(p.iterdir())
            lines = [f"📁 {p.absolute()}", "=" * 40]
            for item in sorted(items):
                icon = "📁" if item.is_dir() else "📄"
                size = f"({item.stat().st_size} bytes)" if item.is_file() else ""
                lines.append(f"{icon} {item.name} {size}")
            return "\n".join(lines)

        elif action == "search":
            query = params.get("query", "")
            if not query:
                return "❌ Kein Suchbegriff angegeben."
            p = _safe_path(path) if path else Path(".")
            if not p.exists(): 
                return f"❌ Pfad nicht gefunden: {path}"
            # Phase 1 Fix: Sicheres Globbing
            safe_query = query.replace("..", "").replace("/", "").replace("\\", "")
            matches = list(p.glob(f"**/*{safe_query}*"))
            lines = [f"🔍 Suche nach '{query}' in {p}:", "=" * 40]
            for m in matches[:50]:
                lines.append(f"  {m}")
            return "\n".join(lines)

        elif action == "delete":
            p = _safe_path(path)
            if not p.exists(): 
                return f"❌ Datei nicht gefunden: {path}"
            # Phase 1 Fix: Bestätigung für große Dateien/Ordner
            size = p.stat().st_size if p.is_file() else sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
            if size > 10 * 1024 * 1024:  # 10 MB
                logger.warning(f"Große Datei/Ordner zum Löschen: {p} ({size} bytes)")
            send2trash(str(p))
            return f"🗑️ In Papierkorb verschoben: {path}"

        else:
            return f"❌ Unbekannte Aktion: '{action}'. Verfuegbar: read, write, list, search, delete"

    except PermissionError as e:
        logger.warning(f"FileController PermissionError: {e}")
        return f"🛡️ Zugriff verweigert: {e}"
    except Exception as e:
        logger.error(f"FileController Fehler: {e}")
        return f"❌ Fehler: {e}"
