"""Web-Suche: Gemini API -> DuckDuckGo Fallback."""
import os, requests
from memory.config_manager import ConfigManager
from core.logger import get_logger

logger = get_logger("WebSearch")

def _gemini_search(query: str, api_key: str) -> str:
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(f"Suche im Internet nach: {query}. Gib eine Zusammenfassung.")
        return response.text
    except Exception as e:
        logger.warning(f"Gemini search failed: {e}")
        raise

def _duckduckgo_search(query: str) -> str:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
            lines = [f"{i+1}. {r['title']}\n   {r['body'][:200]}...\n   {r['href']}" for i, r in enumerate(results)]
            return "\n\n".join(lines)
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed: {e}")
        return f"Suche fehlgeschlagen: {e}"

def web_search(parameters=None, response=None, player=None, session_memory=None) -> str:
    params = parameters or {}
    query = params.get("query", "").strip()
    mode = params.get("mode", "search")
    if not query:
        return "Kein Suchbegriff angegeben."
    if player:
        try: player.write_log(f"[WebSearch] {query}")
        except: pass
    cfg = ConfigManager()
    api_key = cfg.get_api_key("gemini_api_key")
    if api_key and mode == "search":
        try:
            return _gemini_search(query, api_key)
        except Exception:
            pass
    return _duckduckgo_search(query)
