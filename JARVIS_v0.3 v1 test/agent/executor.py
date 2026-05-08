"""Task-Executor mit Retry (3x), Replan (2x) und Tool-Routing."""
import time, traceback
from typing import Optional, Dict, Any
from agent.planner import Planner
from agent.error_handler import ErrorHandler
from core.logger import get_logger
from core.voice.engine import TTSEngine

logger = get_logger("Agent")

class AgentExecutor:
    def __init__(self):
        self.planner = Planner()
        self.error_handler = ErrorHandler()
        self.tts = TTSEngine()
        self._history: list = []
        self._max_retries = 3
        self._max_replans = 2

    def execute(self, user_input: str, speak=None, cancel_flag=None) -> str:
        """Fuehrt einen Benutzerbefehl aus und gibt das ECHTE Ergebnis zurueck."""
        if cancel_flag and cancel_flag.is_set():
            return "❌ Aufgabe abgebrochen."

        # Plan erstellen
        plan = self.planner.plan(user_input)
        if not plan or "tool" not in plan:
            return "❌ Konnte keinen Plan fuer diesen Befehl erstellen."

        tool_name = plan["tool"]
        params = plan.get("params", {})

        logger.info(f"[Agent] Tool: {tool_name}, Params: {params}")

        # Versuche Tool auszufuehren mit Retry
        for attempt in range(1, self._max_retries + 1):
            if cancel_flag and cancel_flag.is_set():
                return "❌ Aufgabe abgebrochen."

            try:
                result = self._call_tool(tool_name, params)
                if result:
                    self._history.append({"tool": tool_name, "params": params, "result": result, "time": time.time()})
                    # FIX: Gib das ECHTE Ergebnis zurueck!
                    return result
                else:
                    return f"⚠️ {tool_name} gab kein Ergebnis zurueck."

            except Exception as e:
                logger.warning(f"[Agent] Versuch {attempt} fehlgeschlagen: {e}")
                if attempt >= self._max_retries:
                    error_msg = self.error_handler.handle(e, tool_name, params)
                    if speak:
                        try: self.tts.speak(f"Fehler: {error_msg}")
                        except: pass
                    return f"❌ Fehler bei {tool_name}: {error_msg}"
                time.sleep(0.5)

        return "❌ Alle Versuche fehlgeschlagen."

    def _call_tool(self, name: str, params: dict) -> str:
        """Ruft eine Action auf und gibt das Ergebnis zurueck."""
        logger.info(f"[Agent] Rufe {name} auf mit {params}")

        if name == "open_app":
            from actions.open_app import open_app
            return open_app(parameters=params, player=self)
        elif name == "browser_control":
            from actions.browser_control import browser_control
            return browser_control(parameters=params, player=self)
        elif name == "computer_settings":
            from actions.computer_settings import computer_settings
            return computer_settings(parameters=params, player=self)
        elif name == "web_search":
            from actions.web_search import web_search
            return web_search(parameters=params, player=self)
        elif name == "file_controller":
            from actions.file_controller import file_controller
            return file_controller(parameters=params, player=self)
        elif name == "screen_processor":
            from actions.screen_processor import screen_processor
            return screen_processor(parameters=params, player=self)
        elif name == "code_helper":
            from actions.code_helper import code_helper
            return code_helper(parameters=params, player=self)
        elif name == "reminder":
            from actions.reminder import reminder
            return reminder(parameters=params, player=self)
        elif name == "send_message":
            from actions.send_message import send_message
            return send_message(parameters=params, player=self)
        elif name == "comfyui":
            from actions.comfyui import comfyui
            return comfyui(parameters=params, player=self)
        elif name == "home_assistant":
            from actions.home_assistant import home_assistant
            return home_assistant(parameters=params, player=self)
        else:
            return f"❌ Unbekanntes Tool: '{name}'"

    def write_log(self, msg: str):
        """Fuer Kompatibilitaet mit Actions die 'player' erwarten."""
        logger.info(msg)

    def reset(self):
        self._history.clear()
