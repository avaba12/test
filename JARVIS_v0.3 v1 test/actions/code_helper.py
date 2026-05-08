"""Python-Code Ausfuehrung in temporärer Datei."""
import tempfile, subprocess, os
from pathlib import Path
from core.logger import get_logger

logger = get_logger("CodeHelper")

def code_helper(parameters=None, response=None, player=None, session_memory=None) -> str:
    params = parameters or {}
    code = params.get("code", "").strip()
    if not code:
        return "❌ Kein Code angegeben."
    if player:
        try: player.write_log(f"[Code] Ausfuehrung...")
        except: pass

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp_path = f.name

        result = subprocess.run(["python", tmp_path], capture_output=True, text=True, timeout=30)
        os.unlink(tmp_path)

        output = result.stdout
        errors = result.stderr

        if result.returncode == 0:
            return f"✅ Code ausgefuehrt:\n```\n{output[:1000]}\n```"
        else:
            return f"❌ Fehler:\n```\n{errors[:1000]}\n```"
    except Exception as e:
        return f"❌ Ausfuehrungsfehler: {e}"
