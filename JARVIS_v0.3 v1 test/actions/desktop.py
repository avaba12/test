"""Desktop-Steuerung — Platzhalter mit informativer Rueckmeldung."""
from core.logger import get_logger
logger = get_logger("Desktop")

def desktop(parameters=None, response=None, player=None, session_memory=None) -> str:
    logger.info("desktop() aufgerufen")
    if player:
        try: player.write_log("[Desktop] Platzhalter")
        except: pass
    return (
        "⚠️ Desktop-Steuerung ist noch ein Platzhalter.\n"
        "Verfuegbar: computer_settings, screen_processor"
    )
