"""ComfyUI Integration fuer Bildgenerierung.

Phase 2 Fix:
- player.write_log() verwenden statt speak()
- Bessere Error-Handling
"""
import json, requests, time, os
from pathlib import Path
from memory.config_manager import ConfigManager
from core.logger import get_logger

logger = get_logger("ComfyUI")

def comfyui(parameters=None, response=None, player=None, session_memory=None) -> str:
    params = parameters or {}
    action = params.get("action", "").lower().strip()
    prompt = params.get("prompt", "")
    cfg = ConfigManager()

    # Phase 2 Fix: player.write_log verwenden (nicht speak)
    if player:
        try:
            player.write_log(f"[ComfyUI] action={action}, prompt={prompt[:50]}")
        except Exception:
            pass

    comfyui_url = cfg.get("comfyui_url", "http://127.0.0.1:8188")
    output_dir = cfg.get("comfyui_output_dir", "outputs/comfyui")

    if action == "generate":
        if not prompt:
            return "Kein Prompt fuer Bildgenerierung angegeben."

        try:
            # Phase 2 Fix: Timeout setzen
            health = requests.get(f"{comfyui_url}/system_stats", timeout=5)
            if health.status_code != 200:
                return f"❌ ComfyUI ist nicht erreichbar unter {comfyui_url}. Bitte starte ComfyUI."

            # Workflow laden
            workflow_json = params.get("workflow", {})
            if not workflow_json:
                workflow_json = {
                    "1": {"inputs": {"text": prompt, "clip": ["4", 0]}, "class_type": "CLIPTextEncode"},
                    "2": {"inputs": {"width": 1024, "height": 1024, "batch_size": 1}, "class_type": "EmptyLatentImage"},
                    "3": {"inputs": {"seed": 0, "steps": 20, "cfg": 7.0, "sampler_name": "euler_ancestral",
                                     "scheduler": "normal", "denoise": 1.0, "model": ["4", 0], "positive": ["1", 0],
                                     "negative": ["1", 1], "latent_image": ["2", 0]}, "class_type": "KSampler"},
                    "4": {"inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}, "class_type": "CheckpointLoaderSimple"},
                    "5": {"inputs": {"samples": ["3", 0], "vae": ["4", 2]}, "class_type": "VAEDecode"},
                    "6": {"inputs": {"filename_prefix": "jarvis", "images": ["5", 0]}, "class_type": "SaveImage"}
                }

            queue_data = {"prompt": workflow_json}
            resp = requests.post(f"{comfyui_url}/prompt", json=queue_data, timeout=30)
            if resp.status_code != 200:
                return f"❌ Fehler beim Queue: {resp.text}"

            prompt_id = resp.json().get("prompt_id", "")
            if not prompt_id:
                return "❌ Keine prompt_id erhalten."

            max_wait = 120
            waited = 0
            while waited < max_wait:
                history = requests.get(f"{comfyui_url}/history/{prompt_id}", timeout=10)
                if history.status_code == 200:
                    data = history.json()
                    if prompt_id in data and data[prompt_id].get("outputs"):
                        outputs = data[prompt_id]["outputs"]
                        images = []
                        for node_id, node_output in outputs.items():
                            if "images" in node_output:
                                for img in node_output["images"]:
                                    images.append(img["filename"])
                        if images:
                            Path(output_dir).mkdir(parents=True, exist_ok=True)
                            return f"✅ Bild generiert! Dateien: {', '.join(images)}"
                time.sleep(2)
                waited += 2

            return "⏳ Timeout beim Warten auf ComfyUI-Ergebnis."

        except requests.exceptions.ConnectionError:
            return f"❌ ComfyUI ist nicht erreichbar unter {comfyui_url}. Bitte starte ComfyUI."
        except requests.exceptions.Timeout:
            return f"⏳ ComfyUI antwortet nicht (Timeout). Server überlastet?"
        except Exception as e:
            return f"❌ ComfyUI Fehler: {e}"

    elif action == "status":
        try:
            resp = requests.get(f"{comfyui_url}/system_stats", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return f"✅ ComfyUI laeuft. GPU: {data.get('gpu', 'N/A')}, RAM: {data.get('ram', 'N/A')}"
            else:
                return f"❌ ComfyUI antwortet mit Status {resp.status_code}"
        except requests.exceptions.Timeout:
            return f"⏳ ComfyUI Status-Check Timeout."
        except Exception as e:
            return f"❌ ComfyUI nicht erreichbar: {e}"

    else:
        return f"Unbekannte ComfyUI-Aktion: '{action}'. Verfuegbar: generate, status"
