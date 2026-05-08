import time, subprocess, platform, shutil, os
from memory.config_manager import ConfigManager
from core.security import SecurityManager

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False

_SYSTEM = platform.system()

_APP_ALIASES = {
    "chrome": {"Windows": "chrome", "Darwin": "Google Chrome", "Linux": "google-chrome"},
    "firefox": {"Windows": "firefox", "Darwin": "Firefox", "Linux": "firefox"},
    "edge": {"Windows": "msedge", "Darwin": "Microsoft Edge", "Linux": "microsoft-edge"},
    "brave": {"Windows": "brave", "Darwin": "Brave Browser", "Linux": "brave-browser"},
    "vscode": {"Windows": "code", "Darwin": "Visual Studio Code", "Linux": "code"},
    "terminal": {"Windows": "wt", "Darwin": "Terminal", "Linux": "gnome-terminal"},
    "cmd": {"Windows": "cmd.exe", "Darwin": "Terminal", "Linux": "bash"},
    "powershell": {"Windows": "powershell.exe", "Darwin": "Terminal", "Linux": "bash"},
    "spotify": {"Windows": "Spotify", "Darwin": "Spotify", "Linux": "spotify"},
    "discord": {"Windows": "Discord", "Darwin": "Discord", "Linux": "discord"},
    "telegram": {"Windows": "Telegram", "Darwin": "Telegram", "Linux": "telegram"},
    "notepad": {"Windows": "notepad.exe", "Darwin": "TextEdit", "Linux": "gedit"},
    "explorer": {"Windows": "explorer.exe", "Darwin": "Finder", "Linux": "nautilus"},
    "obsidian": {"Windows": "Obsidian", "Darwin": "Obsidian", "Linux": "obsidian"},
    "steam": {"Windows": "steam", "Darwin": "Steam", "Linux": "steam"},
    "youtube": {"Windows": "chrome", "Darwin": "Google Chrome", "Linux": "google-chrome"},
    "youtube.com": {"Windows": "chrome", "Darwin": "Google Chrome", "Linux": "google-chrome"},
}

def _normalize(raw: str) -> str:
    key = raw.lower().strip()
    if key in _APP_ALIASES:
        return _APP_ALIASES[key].get(_SYSTEM, raw)
    for alias_key, os_map in _APP_ALIASES.items():
        if alias_key in key or key in alias_key:
            return os_map.get(_SYSTEM, raw)
    return raw

def _is_allowed(app_name: str) -> bool:
    cfg = ConfigManager()
    allowed = cfg.get("allowed_apps", [])
    if not allowed: 
        return True
    normalized = app_name.lower().strip()
    for allowed_app in allowed:
        if allowed_app.lower() in normalized or normalized in allowed_app.lower():
            return True
    return False

def _launch_windows(app_name: str) -> bool:
    # Phase 1 Fix: Verwende shell=False überall

    # Versuche os.startfile() zuerst (am zuverlaessigsten auf Windows)
    try:
        if app_name.endswith(".exe") or app_name.startswith("http") or ":" in app_name:
            os.startfile(app_name)
            time.sleep(1.5)
            return True
    except Exception:
        pass

    # Versuche PATH
    exe_name = app_name if app_name.endswith(".exe") else app_name + ".exe"
    found = shutil.which(app_name) or shutil.which(exe_name) or shutil.which(app_name.split(".")[0])
    if found:
        try:
            # Phase 1 Fix: shell=False, Liste als Argument
            subprocess.Popen([found], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False)
            time.sleep(1.5)
            return True
        except Exception:
            pass

    # Fallback: Win+S Suche
    try:
        import pyautogui
        pyautogui.PAUSE = 0.1
        pyautogui.press("win")
        time.sleep(0.7)
        pyautogui.write(app_name, interval=0.05)
        time.sleep(0.9)
        pyautogui.press("enter")
        time.sleep(2.5)
        return True
    except Exception:
        pass
    return False

def _launch_macos(app_name: str) -> bool:
    try:
        # Phase 1 Fix: shell=False
        result = subprocess.run(["open", "-a", app_name], capture_output=True, timeout=8, shell=False)
        if result.returncode == 0:
            time.sleep(1.0)
            return True
    except Exception:
        pass
    binary = shutil.which(app_name) or shutil.which(app_name.lower())
    if binary:
        try:
            subprocess.Popen([binary], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False)
            time.sleep(1.0)
            return True
        except Exception:
            pass
    return False

def _launch_linux(app_name: str) -> bool:
    binary = shutil.which(app_name) or shutil.which(app_name.lower())
    if binary:
        try:
            subprocess.Popen([binary], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False)
            time.sleep(1.0)
            return True
        except Exception:
            pass
    return False

_OS_LAUNCHERS = {"Windows": _launch_windows, "Darwin": _launch_macos, "Linux": _launch_linux}

def open_app(parameters=None, response=None, player=None, session_memory=None) -> str:
    app_name = (parameters or {}).get("app_name", "").strip()
    if not app_name:
        return "❌ Kein App-Name angegeben."

    # Phase 1 Fix: Security-Sanitization
    security = SecurityManager()
    try:
        app_name = security.sanitize_app_name(app_name)
    except ValueError as e:
        return f"🛡️ Ungültiger App-Name: {e}"

    # Spezialfall: Wenn der Name wie eine URL aussieht, oeffne im Browser
    if app_name.startswith("http") or app_name.endswith(".com") or app_name.endswith(".de") or "." in app_name:
        # Phase 1 Fix: URL validieren
        sanitized = security.sanitize_url(app_name)
        if sanitized is None:
            return f"🛡️ URL '{app_name}' wurde aus Sicherheitsgründen blockiert."
        from actions.browser_control import browser_control
        return browser_control({"action": "go_to", "url": sanitized}, player=player)

    if not _is_allowed(app_name):
        return f"❌ App '{app_name}' ist nicht in der erlaubten Liste."

    launcher = _OS_LAUNCHERS.get(_SYSTEM)
    if launcher is None:
        return f"❌ Nicht unterstuetztes Betriebssystem: {_SYSTEM}"

    normalized = _normalize(app_name)
    print(f"[open_app] Starte: '{app_name}' -> '{normalized}' ({_SYSTEM})")
    if player:
        try: 
            player.write_log(f"[open_app] {app_name}")
        except: 
            pass

    try:
        if launcher(normalized):
            return f"✅ {app_name} geoeffnet."
        if normalized.lower() != app_name.lower():
            if launcher(app_name):
                return f"✅ {app_name} geoeffnet."
        return f"⚠️ Konnte {app_name} nicht oeffnen. Bitte pruefe ob die App installiert ist."
    except Exception as e:
        return f"❌ Fehler beim Oeffnen von {app_name}: {e}"
