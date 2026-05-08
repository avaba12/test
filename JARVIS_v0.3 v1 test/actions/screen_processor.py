"""Screen-Processor: Screenshots und OCR."""
import time
from pathlib import Path
from core.logger import get_logger

try:
    import pyautogui
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

logger = get_logger("Screen")

def screen_processor(parameters=None, response=None, player=None, session_memory=None) -> str:
    params = parameters or {}
    action = params.get("action", "screenshot").lower().strip()
    if player:
        try: player.write_log(f"[Screen] {action}")
        except: pass
    if action == "screenshot":
        if not _PYAUTOGUI:
            return "❌ pyautogui nicht installiert"
        try:
            out_dir = Path("outputs/screenshots")
            out_dir.mkdir(parents=True, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            path = out_dir / f"screenshot_{ts}.png"
            pyautogui.screenshot().save(str(path))
            return f"✅ Screenshot: {path}"
        except Exception as e:
            return f"❌ Fehler: {e}"
    elif action == "ocr":
        return "⚠️ OCR noch nicht implementiert."
    return f"❌ Unbekannt: {action}"
