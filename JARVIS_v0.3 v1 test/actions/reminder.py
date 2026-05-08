"""Reminder / Timer — Platzhalter mit informativer Rueckmeldung."""
from core.logger import get_logger
logger = get_logger("Reminder")

def reminder(parameters=None, response=None, player=None, session_memory=None) -> str:
    params = parameters or {}
    text = params.get("text", "")
    timer = params.get("time", "5m")
    if player:
        try: player.write_log(f"[Reminder] {text[:50]} in {timer}")
        except: pass
    try:
        if timer.endswith("m"): s = int(timer[:-1]) * 60
        elif timer.endswith("h"): s = int(timer[:-1]) * 3600
        elif timer.endswith("s"): s = int(timer[:-1])
        else: s = int(timer)
    except ValueError:
        s = 300
    logger.info(f"Reminder: {text} in {s}s")
    return f"⏰ Erinnerung: {text[:50]} in {s//60}m {s%60}s\n⚠️ Hintergrund-Timer noch nicht aktiv."
