"""GPU-Monitoring: AMD ROCm, NVIDIA, Intel + WMI-Fallback.

Phase 4 Fixes:
- Thread-sicheres Caching mit Lock
- Auto-Discovery fuer rocm-smi via shutil.which()
"""
import subprocess, platform, shutil, os, time, re, threading
from pathlib import Path
from typing import Dict, Optional
from memory.config_manager import ConfigManager
from core.logger import get_logger

logger = get_logger("GPU")

class GPUMonitor:
    def __init__(self):
        self.cfg = ConfigManager()
        self._last_info = {}
        self._last_check = 0
        self._cache_lock = threading.Lock()

    def get_info(self) -> Dict:
        now = time.time()
        with self._cache_lock:
            if now - self._last_check < 2:
                return self._last_info
            self._last_check = now
        info = {"name": "Unknown", "vram_total_mb": 0, "vram_used_mb": 0, "temperature_c": 0, "load_percent": 0}
        amd_info = self._get_amd_rocm_info()
        if amd_info:
            info = amd_info
        else:
            amd_wmi = self._get_amd_wmi_info()
            if amd_wmi:
                info = amd_wmi
            else:
                nvidia_info = self._get_nvidia_info()
                if nvidia_info:
                    info = nvidia_info
                else:
                    intel_info = self._get_intel_info()
                    if intel_info:
                        info = intel_info
        with self._cache_lock:
            self._last_info = info
        return info

    def _get_amd_rocm_info(self) -> Optional[Dict]:
        try:
            rocm_smi = shutil.which("rocm-smi")
            if not rocm_smi:
                rocm_path = self.cfg.get("rocm_path", "")
                if rocm_path:
                    candidate = Path(rocm_path) / ("rocm-smi.exe" if platform.system() == "Windows" else "rocm-smi")
                    if candidate.exists():
                        rocm_smi = str(candidate)
            if not rocm_smi:
                return None
            result = subprocess.run([rocm_smi, "--showmeminfo", "vram", "--showtemp", "--showuse"],
                capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                return None
            lines = result.stdout.split("\n")
            name, vram_total, vram_used, temp, load = "AMD GPU", 0, 0, 0, 0
            for line in lines:
                if "GPU" in line and ":" in line:
                    parts = line.split(":")
                    if len(parts) > 1: name = parts[1].strip().split()[0]
                if "VRAM" in line and "Total" in line:
                    try: vram_total = int(line.split()[-1]) // 1024 // 1024
                    except: pass
                if "VRAM" in line and "Used" in line:
                    try: vram_used = int(line.split()[-1]) // 1024 // 1024
                    except: pass
                if "Temperature" in line:
                    try: temp = int(line.split()[-1].replace("C", "").replace("°", ""))
                    except: pass
                if "GPU use" in line or "GPU Use" in line:
                    try: load = int(line.split()[-1].replace("%", ""))
                    except: pass
            return {"name": name, "vram_total_mb": vram_total, "vram_used_mb": vram_used, "temperature_c": temp, "load_percent": load}
        except Exception as e:
            logger.debug(f"AMD ROCm check failed: {e}")
            return None

    def _get_amd_wmi_info(self) -> Optional[Dict]:
        if platform.system() != "Windows":
            return None
        try:
            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name,adapterram", "/format:csv"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                return None
            lines = result.stdout.strip().split("\n")
            for line in lines[1:]:
                parts = line.split(",")
                if len(parts) >= 3:
                    name = parts[1].strip()
                    if "amd" in name.lower() or "radeon" in name.lower():
                        try:
                            vram_bytes = int(parts[2].strip())
                            vram_mb = vram_bytes // 1024 // 1024
                        except:
                            vram_mb = 0
                        return {"name": name, "vram_total_mb": vram_mb, "vram_used_mb": 0, "temperature_c": 0, "load_percent": 0, "note": "ROCm nicht installiert"}
            return None
        except Exception as e:
            logger.debug(f"AMD WMI check failed: {e}")
            return None

    def _get_nvidia_info(self) -> Optional[Dict]:
        try:
            nvidia_smi = shutil.which("nvidia-smi")
            if not nvidia_smi:
                return None
            result = subprocess.run([nvidia_smi, "--query-gpu=name,memory.total,memory.used,temperature.gpu,utilization.gpu",
                "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                return None
            parts = result.stdout.strip().split(", ")
            if len(parts) >= 5:
                return {"name": parts[0].strip(), "vram_total_mb": int(float(parts[1].strip())),
                    "vram_used_mb": int(float(parts[2].strip())), "temperature_c": int(float(parts[3].strip())),
                    "load_percent": int(float(parts[4].strip()))}
            return None
        except Exception as e:
            logger.debug(f"NVIDIA GPU check failed: {e}")
            return None

    def _get_intel_info(self) -> Optional[Dict]:
        try:
            intel_gpu_top = shutil.which("intel_gpu_top")
            if not intel_gpu_top:
                return None
            return {"name": "Intel GPU", "vram_total_mb": 0, "vram_used_mb": 0, "temperature_c": 0, "load_percent": 0}
        except Exception:
            return None

    def clear_vram(self) -> str:
        try:
            import ollama
            host = self.cfg.get("ollama_host", "http://localhost:11434")
            client = ollama.Client(host=host)
            client.ps()
            return "✅ VRAM geleert. Ollama-Modelle entladen."
        except Exception as e:
            return f"⚠️ VRAM-Clear: {e}"
