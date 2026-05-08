"""Skill-Manager mit 11 Skills, Master-Modi und JSON Import/Export."""
import json
from pathlib import Path
from typing import Dict, List
from memory.config_manager import ConfigManager

class SkillManager:
    SKILLS = {
        "web_search": {"name": "Web-Suche", "desc": "DuckDuckGo + Gemini", "builtin": True},
        "file_access": {"name": "Dateizugriff", "desc": "Lesen, Schreiben, Suchen", "builtin": True},
        "comfyui": {"name": "ComfyUI", "desc": "Bildgenerierung", "builtin": True},
        "pc_control": {"name": "PC-Steuerung", "desc": "Tastatur, Maus, System", "builtin": True},
        "plugins": {"name": "Plugins", "desc": "Erweiterungen laden", "builtin": True},
        "telegram": {"name": "Telegram", "desc": "Bot-Nachrichten", "builtin": True},
        "discord": {"name": "Discord", "desc": "Webhook-Nachrichten", "builtin": True},
        "home_assistant": {"name": "Home Assistant", "desc": "Smart Home", "builtin": True},
        "obsidian": {"name": "Obsidian", "desc": "Notizen verwalten", "builtin": True},
        "voice_control": {"name": "Sprachsteuerung", "desc": "Wake-Word, STT, TTS", "builtin": True},
        "rag": {"name": "RAG", "desc": "Dokumenten-Suche", "builtin": True},
    }

    def __init__(self):
        self.cfg = ConfigManager()

    def is_enabled(self, skill: str) -> bool:
        skills = self.cfg.get("skills", {})
        return skills.get(skill, False)

    def add_skill(self, key: str, name: str, desc: str, permissions: List[str]) -> bool:
        if key in self.SKILLS:
            return False
        self.SKILLS[key] = {"name": name, "desc": desc, "permissions": permissions, "builtin": False}
        return True

    def delete_skill(self, key: str) -> bool:
        if key not in self.SKILLS or self.SKILLS[key].get("builtin", True):
            return False
        del self.SKILLS[key]
        return True

    def export_skills(self, path: Path) -> bool:
        try:
            data = {k: {"name": v["name"], "desc": v["desc"]} for k, v in self.SKILLS.items() if not v.get("builtin", True)}
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            return True
        except Exception:
            return False

    def import_skills(self, path: Path):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            count = 0
            for key, info in data.items():
                if self.add_skill(key, info["name"], info["desc"], info.get("permissions", [])):
                    count += 1
            return count, None
        except Exception as e:
            return 0, str(e)
