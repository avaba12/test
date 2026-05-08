"""Retry/Skip/Replan/Abort Entscheidungen."""
import traceback

class ErrorHandler:
    def handle(self, error: Exception, tool_name: str, params: dict) -> str:
        error_str = str(error).lower()

        if "not found" in error_str or "nicht gefunden" in error_str:
            return f"{tool_name} nicht gefunden. Bitte pruefe die Installation."
        elif "permission" in error_str or "zugriff" in error_str:
            return f"Zugriff verweigert fuer {tool_name}. Admin-Rechte noetig?"
        elif "timeout" in error_str or "zeitueberschreitung" in error_str:
            return f"{tool_name} hat zu lange gebraucht. Bitte erneut versuchen."
        elif "connection" in error_str or "verbindung" in error_str:
            return f"Keine Verbindung fuer {tool_name}. Internet oder Server erreichbar?"
        else:
            return f"Fehler in {tool_name}: {error}"
