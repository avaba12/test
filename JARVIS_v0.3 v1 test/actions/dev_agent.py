"""Dev-Agent — Platzhalter mit informativer Rueckmeldung."""
from core.logger import get_logger
logger = get_logger("DevAgent")

def dev_agent(parameters=None, response=None, player=None, session_memory=None) -> str:
    logger.info("dev_agent() aufgerufen")
    if player:
        try: player.write_log("[DevAgent] Platzhalter")
        except: pass
    return (
        "⚠️ Dev-Agent ist noch ein Platzhalter.\n"
        "Nutze stattdessen den Code-Modus im Chat."
    )
