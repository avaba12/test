"""Home Assistant Integration fuer Smart Home Steuerung.

Phase 2 Fix:
- Einheitliche Timeout-Werte (10s)
"""
import requests, json
from memory.config_manager import ConfigManager
from core.logger import get_logger

logger = get_logger("HomeAssistant")

def home_assistant(parameters=None, response=None, player=None, session_memory=None) -> str:
    params = parameters or {}
    action = params.get("action", "").lower().strip()
    entity_id = params.get("entity_id", "")

    cfg = ConfigManager()
    ha_url = cfg.get("home_assistant_url", "")
    ha_token = cfg.get_api_key("home_assistant_token")

    if not ha_url or not ha_token:
        return "❌ Home Assistant URL oder Token nicht konfiguriert."

    headers = {
        "Authorization": f"Bearer {ha_token}",
        "Content-Type": "application/json"
    }

    try:
        if action == "status":
            resp = requests.get(f"{ha_url}/api/", headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return f"✅ Home Assistant verbunden. Version: {data.get('version', 'N/A')}"
            return f"❌ Fehler: {resp.status_code}"

        elif action == "toggle":
            if not entity_id: 
                return "Keine entity_id angegeben."
            resp = requests.post(f"{ha_url}/api/services/homeassistant/toggle",
                                 headers=headers, json={"entity_id": entity_id}, timeout=10)
            return f"✅ {entity_id} umgeschaltet." if resp.status_code == 200 else f"❌ Fehler: {resp.status_code}"

        elif action == "turn_on":
            if not entity_id: 
                return "Keine entity_id angegeben."
            resp = requests.post(f"{ha_url}/api/services/homeassistant/turn_on",
                                 headers=headers, json={"entity_id": entity_id}, timeout=10)
            return f"✅ {entity_id} eingeschaltet." if resp.status_code == 200 else f"❌ Fehler: {resp.status_code}"

        elif action == "turn_off":
            if not entity_id: 
                return "Keine entity_id angegeben."
            resp = requests.post(f"{ha_url}/api/services/homeassistant/turn_off",
                                 headers=headers, json={"entity_id": entity_id}, timeout=10)
            return f"✅ {entity_id} ausgeschaltet." if resp.status_code == 200 else f"❌ Fehler: {resp.status_code}"

        elif action == "list_entities":
            resp = requests.get(f"{ha_url}/api/states", headers=headers, timeout=10)
            if resp.status_code == 200:
                entities = resp.json()
                lines = [f"📋 Entitäten ({len(entities)} total):", "=" * 50]
                for e in entities[:50]:
                    lines.append(f"• {e['entity_id']} = {e['state']}")
                return "\n".join(lines)
            return f"❌ Fehler: {resp.status_code}"

        elif action == "get_state":
            if not entity_id: 
                return "Keine entity_id angegeben."
            resp = requests.get(f"{ha_url}/api/states/{entity_id}", headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return f"✅ {entity_id}: {data.get('state', 'N/A')}\nAttributes: {json.dumps(data.get('attributes', {}), indent=2)}"
            return f"❌ Fehler: {resp.status_code}"

        else:
            return f"Unbekannte Aktion: '{action}'. Verfuegbar: status, toggle, turn_on, turn_off, list_entities, get_state"

    except requests.exceptions.ConnectionError:
        return f"❌ Home Assistant nicht erreichbar unter {ha_url}."
    except requests.exceptions.Timeout:
        return f"⏳ Home Assistant Timeout. Server antwortet nicht."
    except Exception as e:
        return f"❌ Home Assistant Fehler: {e}"
