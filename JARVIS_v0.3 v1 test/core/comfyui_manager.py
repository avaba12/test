"""ComfyUI Workflow-Manager: JSON parsen, Parameter erkennen, UI dynamisch generieren.

Phase 2 Fix:
- requests mit timeout
"""
import json, os
from pathlib import Path
from typing import Dict, List, Any, Optional
from memory.config_manager import ConfigManager
from core.logger import get_logger

logger = get_logger("ComfyUI")

NODE_PARAM_MAP = {
    "CLIPTextEncode": {
        "text": {"label": "Prompt", "type": "text", "default": ""}
    },
    "KSampler": {
        "seed": {"label": "Seed", "type": "int", "default": -1, "min": -1, "max": 999999999},
        "steps": {"label": "Steps", "type": "int", "default": 20, "min": 1, "max": 100},
        "cfg": {"label": "CFG Scale", "type": "float", "default": 7.0, "min": 1.0, "max": 20.0},
        "sampler_name": {"label": "Sampler", "type": "choice", "default": "euler_ancestral",
            "choices": ["euler", "euler_ancestral", "heun", "dpm_2", "dpm_2_ancestral",
                        "lms", "dpm_fast", "dpm_adaptive", "dpmpp_2s", "dpmpp_sde",
                        "dpmpp_2m", "dpmpp_2m_sde", "ddim", "uni_pc", "uni_pc_bh2"]},
        "scheduler": {"label": "Scheduler", "type": "choice", "default": "normal",
            "choices": ["normal", "karras", "exponential", "sgm_uniform", "simple", "ddim_uniform"]},
        "denoise": {"label": "Denoise", "type": "float", "default": 1.0, "min": 0.0, "max": 1.0},
    },
    "EmptyLatentImage": {
        "width": {"label": "Width", "type": "choice", "default": 1024,
            "choices": [256, 512, 768, 1024, 1280, 1536, 2048]},
        "height": {"label": "Height", "type": "choice", "default": 1024,
            "choices": [256, 512, 768, 1024, 1280, 1536, 2048]},
        "batch_size": {"label": "Batch Size", "type": "int", "default": 1, "min": 1, "max": 10},
    },
    "CheckpointLoaderSimple": {
        "ckpt_name": {"label": "Checkpoint", "type": "text", "default": "sd_xl_base_1.0.safetensors"}
    },
    "LoadImage": {
        "image": {"label": "Input Image", "type": "text", "default": ""}
    },
    "SaveImage": {
        "filename_prefix": {"label": "Filename Prefix", "type": "text", "default": "jarvis"}
    },
    "AnimateDiffLoaderV1": {
        "model_name": {"label": "Motion Module", "type": "text", "default": "mm_sd_v15_v2.ckpt"}
    },
    "LoadVideo": {
        "video": {"label": "Input Video", "type": "text", "default": ""},
        "frame_load_cap": {"label": "Frame Cap", "type": "int", "default": 16, "min": 1, "max": 128},
    },
    "VHS_VideoCombine": {
        "frame_rate": {"label": "FPS", "type": "int", "default": 8, "min": 1, "max": 60},
        "loop_count": {"label": "Loops", "type": "int", "default": 0, "min": 0, "max": 10},
    },
    "RiffusionNode": {
        "prompt": {"label": "Prompt", "type": "text", "default": "ambient music"},
        "duration": {"label": "Duration (s)", "type": "float", "default": 5.0, "min": 1.0, "max": 30.0},
        "tempo": {"label": "Tempo (BPM)", "type": "int", "default": 120, "min": 60, "max": 180},
    },
}

class ComfyUIWorkflowManager:
    def __init__(self):
        self.cfg = ConfigManager()
        self.workflows_dir = Path("workflows")
        self._workflows = {"bilder": {}, "videos": {}, "musik": {}}
        self._scan_workflows()

    def _scan_workflows(self):
        for category in ["bilder", "videos", "musik"]:
            cat_dir = self.workflows_dir / category
            if not cat_dir.exists():
                continue
            for json_file in cat_dir.glob("*.json"):
                try:
                    data = json.loads(json_file.read_text(encoding="utf-8"))
                    name = json_file.stem
                    self._workflows[category][name] = {
                        "path": str(json_file),
                        "data": data,
                        "params": self._extract_params(data)
                    }
                except Exception as e:
                    logger.warning(f"Workflow {json_file}: {e}")
        logger.info(f"Workflows geladen: Bilder={len(self._workflows['bilder'])}, "
                    f"Videos={len(self._workflows['videos'])}, Musik={len(self._workflows['musik'])}")

    def _extract_params(self, workflow_data: dict) -> List[Dict]:
        params = []
        seen = set()
        for node_id, node in workflow_data.items():
            if not isinstance(node, dict):
                continue
            class_type = node.get("class_type", "")
            inputs = node.get("inputs", {})
            if class_type in NODE_PARAM_MAP:
                for key, meta in NODE_PARAM_MAP[class_type].items():
                    if key in inputs:
                        param_id = f"{class_type}_{key}"
                        if param_id in seen:
                            param_id = f"{param_id}_{node_id}"
                        seen.add(param_id)
                        params.append({
                            "id": param_id, "node_id": node_id, "node_type": class_type,
                            "key": key, "label": meta["label"], "type": meta["type"],
                            "default": inputs.get(key, meta["default"]),
                            "current": inputs.get(key, meta["default"]),
                            "min": meta.get("min"), "max": meta.get("max"),
                            "choices": meta.get("choices"),
                        })
        return params

    def get_workflows(self, category: str) -> Dict[str, Dict]:
        return self._workflows.get(category, {})

    def get_workflow(self, category: str, name: str) -> Optional[Dict]:
        return self._workflows.get(category, {}).get(name)

    def apply_params(self, category: str, name: str, param_values: Dict[str, Any]) -> dict:
        wf = self.get_workflow(category, name)
        if not wf:
            return {}
        workflow = json.loads(json.dumps(wf["data"]))
        for param_id, value in param_values.items():
            for p in wf["params"]:
                if p["id"] == param_id:
                    node_id = p["node_id"]
                    key = p["key"]
                    if node_id in workflow and "inputs" in workflow[node_id]:
                        workflow[node_id]["inputs"][key] = value
                    break
        return workflow

    def add_workflow(self, category: str, name: str, json_data: dict, source_path: str = "") -> bool:
        try:
            cat_dir = self.workflows_dir / category
            cat_dir.mkdir(parents=True, exist_ok=True)
            target = cat_dir / f"{name}.json"
            target.write_text(json.dumps(json_data, indent=2, ensure_ascii=False), encoding="utf-8")
            self._workflows[category][name] = {
                "path": str(target), "data": json_data,
                "params": self._extract_params(json_data)
            }
            return True
        except Exception as e:
            logger.error(f"Workflow hinzufuegen fehlgeschlagen: {e}")
            return False

    def delete_workflow(self, category: str, name: str) -> bool:
        try:
            wf = self._workflows.get(category, {}).get(name)
            if wf and wf.get("path"):
                Path(wf["path"]).unlink(missing_ok=True)
                if name in self._workflows.get(category, {}):
                    del self._workflows[category][name]
                return True
        except Exception as e:
            logger.error(f"Workflow loeschen fehlgeschlagen: {e}")
        return False

    def get_categories(self) -> List[str]:
        return ["bilder", "videos", "musik"]

    def reload(self):
        self._workflows = {"bilder": {}, "videos": {}, "musik": {}}
        self._scan_workflows()
