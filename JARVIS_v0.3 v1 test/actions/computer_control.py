"""Tastatur/Maus, Screenshots, Hotkeys via pyautogui."""
import time
from core.logger import get_logger

logger = get_logger("ComputerControl")

def computer_control(parameters=None, response=None, player=None, session_memory=None) -> str:
    params = parameters or {}
    action = params.get("action", "").lower().strip()

    if player:
        try: player.write_log(f"[PC] {action}")
        except: pass

    try:
        import pyautogui

        if action == "click":
            x = params.get("x", 0)
            y = params.get("y", 0)
            pyautogui.click(x, y)
            return f"✅ Geklickt bei ({x}, {y})"

        elif action == "type":
            text = params.get("text", "")
            pyautogui.typewrite(text, interval=0.05)
            return f"✅ Text eingegeben: {text[:50]}..."

        elif action == "hotkey":
            keys = params.get("keys", [])
            pyautogui.hotkey(*keys)
            return f"✅ Hotkey: {'+'.join(keys)}"

        elif action == "move":
            x = params.get("x", 0)
            y = params.get("y", 0)
            pyautogui.moveTo(x, y, duration=0.5)
            return f"✅ Maus bewegt zu ({x}, {y})"

        else:
            return f"❌ Unbekannte Aktion: '{action}'"

    except ImportError:
        return "❌ pyautogui nicht installiert. Fuehre aus: pip install pyautogui"
    except Exception as e:
        return f"❌ Fehler: {e}"
