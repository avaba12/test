"""TTS-Engine: Piper (Offline) -> Edge-TTS (Online) -> pyttsx3 (Fallback).

Phase 2 Fixes:
- TTS-Queue auf 50 Einträge begrenzt (Memory-Schutz)
- Thread-sicheres Queue-Management
- Bessere Temp-File-Cleanup
- Graceful Shutdown bei Engine-Wechsel
"""
import threading, queue, time, os, subprocess, tempfile, shutil
from pathlib import Path
from typing import Optional
from memory.config_manager import ConfigManager
from core.logger import get_logger

logger = get_logger("TTS")

class TTSEngine:
    def __init__(self):
        self.cfg = ConfigManager()
        # Phase 2 Fix: Queue mit maxsize
        self._queue = queue.Queue(maxsize=50)
        self._thread = threading.Thread(target=self._process_queue, daemon=True, name="TTSThread")
        self._thread.start()
        self._piper_checked = False
        self._piper_available = False
        self._edge_available = None
        self._current_engine = None
        self._shutdown = threading.Event()

    def _check_piper_once(self):
        if self._piper_checked:
            return self._piper_available
        piper_exe = Path("models/piper/piper.exe")
        has_exe = piper_exe.exists()
        model_dir = Path("models/piper")
        has_model = any(model_dir.glob("*.onnx")) if model_dir.exists() else False
        has_json = any(model_dir.glob("*.json")) if model_dir.exists() else False
        self._piper_available = has_exe and has_model and has_json
        self._piper_checked = True
        if self._piper_available:
            logger.info(f"✅ Piper TTS verfuegbar")
        else:
            missing = []
            if not has_exe: missing.append("piper.exe")
            if not has_model: missing.append("*.onnx Model")
            if not has_json: missing.append("*.json Config")
            logger.warning(f"⚠️ Piper unvollstaendig — fehlt: {', '.join(missing)}")
        return self._piper_available

    def _check_edge(self):
        if self._edge_available is not None:
            return self._edge_available
        try:
            import edge_tts
            self._edge_available = True
            return True
        except ImportError:
            self._edge_available = False
            return False

    def speak(self, text: str, engine: Optional[str] = None):
        if not text or not text.strip():
            return
        clean_text = self._clean_for_tts(text.strip())
        if clean_text:
            try:
                # Phase 2 Fix: Nicht blockieren, alte Einträge verwerfen
                self._queue.put_nowait(clean_text)
            except queue.Full:
                logger.warning("TTS-Queue voll — Text verworfen (zu viele Anfragen)")

    def _clean_for_tts(self, text: str) -> str:
        import re
        text = re.sub(r'\`\`\`.*?\`\`\`', '', text, flags=re.DOTALL)
        text = re.sub(r'\`[^\`]+\`', '', text)
        text = re.sub(r'\*\*([^*]+)\*\*', r'', text)
        text = re.sub(r'\*([^*]+)\*', r'', text)
        text = re.sub(r'#+ ', '', text)
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'www\.\S+', '', text)
        if len(text) > 500:
            text = text[:497] + "..."
        return text.strip()

    def stop(self):
        """Phase 2 Fix: Graceful Shutdown mit Event."""
        self._shutdown.set()
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def _process_queue(self):
        while not self._shutdown.is_set():
            try:
                text = self._queue.get(timeout=1)
                self._speak_internal(text)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"TTS queue error: {e}")

    def _speak_internal(self, text: str):
        engine = self.cfg.get("tts_engine", "piper")
        voice = self.cfg.get("piper_model", "") or self.cfg.get("tts_voice", "thorsten-de-medium")
        speed = self.cfg.get("tts_speed", 1.0)
        volume = self.cfg.get("tts_volume", 0.9)
        if engine == "piper":
            if self._check_piper_once():
                self._speak_piper(text, voice, speed, volume)
            else:
                self._speak_pyttsx3(text, speed, volume)
        elif engine == "edge":
            if self._check_edge():
                self._speak_edge(text, voice, speed, volume)
            else:
                logger.warning("Edge-TTS nicht verfuegbar — Fallback zu pyttsx3")
                self._speak_pyttsx3(text, speed, volume)
        elif engine == "pyttsx3":
            self._speak_pyttsx3(text, speed, volume)
        else:
            logger.warning(f"Unbekannte TTS-Engine: {engine}")

    def _speak_piper(self, text: str, voice: str, speed: float, volume: float):
        txt_path = None
        wav_path = None
        try:
            piper_exe = Path("models/piper/piper.exe")
            model_dir = Path("models/piper")
            model_file = model_dir / f"{voice}.onnx"
            json_file = model_dir / f"{voice}.json"
            if not model_file.exists():
                onnx_files = list(model_dir.glob("*.onnx"))
                if onnx_files:
                    model_file = onnx_files[0]
                    json_file = model_file.with_suffix(".json")
                else:
                    logger.warning("Kein Piper-Modell gefunden")
                    self._speak_pyttsx3(text, speed, volume)
                    return

            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
                f.write(text)
                txt_path = f.name
            wav_path = txt_path.replace(".txt", ".wav")

            cmd = [
                str(piper_exe), "-m", str(model_file),
                "-c", str(json_file) if json_file.exists() else str(model_file).replace(".onnx", ".json"),
                "-f", txt_path, "-o", wav_path, "--length_scale", str(1.0 / speed)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and Path(wav_path).exists():
                self._play_wav(wav_path, volume)
            else:
                logger.warning(f"Piper Fehler: {result.stderr}")
                self._speak_pyttsx3(text, speed, volume)
        except Exception as e:
            logger.error(f"Piper TTS error: {e}")
            self._speak_pyttsx3(text, speed, volume)
        finally:
            # Phase 2 Fix: Zuverlässiges Cleanup
            if txt_path and os.path.exists(txt_path):
                try:
                    os.unlink(txt_path)
                except Exception:
                    pass
            if wav_path and os.path.exists(wav_path):
                try:
                    os.unlink(wav_path)
                except Exception:
                    pass

    def _speak_edge(self, text: str, voice: str, speed: float, volume: float):
        mp3_path = None
        try:
            import edge_tts
            import asyncio
            edge_voice = voice
            if "thorsten" in voice.lower(): 
                edge_voice = "de-DE-KillianNeural"
            elif "eva" in voice.lower(): 
                edge_voice = "de-DE-SeraphinaNeural"

            async def _edge_speak():
                nonlocal mp3_path
                communicate = edge_tts.Communicate(text, edge_voice, rate=f"+{int((speed-1)*100)}%")
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    mp3_path = f.name
                await communicate.save(mp3_path)
                self._play_mp3(mp3_path, volume)

            asyncio.run(_edge_speak())
        except Exception as e:
            logger.error(f"Edge TTS error: {e}")
            self._speak_pyttsx3(text, speed, volume)
        finally:
            if mp3_path and os.path.exists(mp3_path):
                try:
                    os.unlink(mp3_path)
                except Exception:
                    pass

    def _speak_pyttsx3(self, text: str, speed: float, volume: float):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", int(200 * speed))
            engine.setProperty("volume", volume)
            voice_id = self.cfg.get("tts_voice", "")
            if voice_id:
                for v in engine.getProperty("voices"):
                    if voice_id in v.id or voice_id in v.name:
                        engine.setProperty("voice", v.id)
                        break
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            logger.error(f"pyttsx3 error: {e}")

    def _play_wav(self, path: str, volume: float):
        try:
            import sounddevice as sd
            import soundfile as sf
            data, samplerate = sf.read(path)
            sd.play(data * volume, samplerate)
            sd.wait()
        except Exception as e:
            logger.error(f"WAV play error: {e}")

    def _play_mp3(self, path: str, volume: float):
        try:
            from pydub import AudioSegment
            import numpy as np
            import sounddevice as sd
            audio = AudioSegment.from_mp3(path)
            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
            if audio.channels == 2: 
                samples = samples.reshape((-1, 2))
            samples = samples / (2**15) * volume
            sd.play(samples, audio.frame_rate)
            sd.wait()
        except Exception as e:
            logger.error(f"MP3 play error: {e}")
