"""STT-Listener: Vosk (offline) -> Google Speech (nur Online) + lokales Wake-Word ohne Key.

Phase 2 Fixes:
- Stream-Cleanup mit try/finally (keine Memory Leaks mehr)
- Bessere Exception-Handling in _listen_loop
- Energie-Schwellwert konfigurierbar
"""
import threading, queue, time, os, sys, struct, math
from pathlib import Path
from typing import Callable, Optional
from memory.config_manager import ConfigManager
from core.logger import get_logger

logger = get_logger("STT")

class STTListener:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self.cfg = ConfigManager()
        self._running = False
        self._muted = False
        self._sleeping = False
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable] = None
        self._wake_callback: Optional[Callable] = None
        self._vosk_model = None
        self._porcupine = None
        self._recorder = None
        self._init_vosk()

    def _init_vosk(self):
        try:
            from vosk import Model
            model_name = self.cfg.get("vosk_model", "vosk-model-small-de-0.15")
            model_path = Path("models") / model_name
            if model_path.exists():
                self._vosk_model = Model(str(model_path))
                logger.info(f"Vosk-Modell geladen: {model_name}")
            else:
                logger.warning(f"Vosk-Modell nicht gefunden: {model_path}")
        except ImportError:
            logger.warning("Vosk nicht installiert")
        except Exception as e:
            logger.warning(f"Vosk-Init fehlgeschlagen: {e}")

    def start(self, on_text: Callable[[str], None], on_wake: Optional[Callable] = None):
        self._callback = on_text
        self._wake_callback = on_wake
        if self._running: 
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="STTListener")
        self._thread.start()
        logger.info("STT-Listener gestartet")

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        # Phase 2 Fix: Recorder auch stoppen
        if self._recorder:
            try:
                self._recorder.stop()
                self._recorder.delete()
            except Exception:
                pass
            self._recorder = None
        if self._porcupine:
            try:
                self._porcupine.delete()
            except Exception:
                pass
            self._porcupine = None
        logger.info("STT-Listener gestoppt")

    def set_mute(self, muted: bool):
        self._muted = muted
        logger.info(f"Mikrofon {'stumm' if muted else 'aktiv'}")

    @property
    def is_muted(self) -> bool: 
        return self._muted
    @property
    def is_sleeping(self) -> bool: 
        return self._sleeping

    def _listen_loop(self):
        stt_engine = self.cfg.get("stt_engine", "vosk")
        offline = self.cfg.get("offline_mode", True)
        use_local_wake = self.cfg.get("use_local_wake_word", True)
        if stt_engine == "none":
            logger.info("STT deaktiviert")
            return
        if use_local_wake:
            logger.info("Lokales Wake-Word aktiv")
            self._local_wake_word_loop()
        elif not offline:
            self._porcupine_wake_word_loop()
        else:
            logger.info("Kein Wake-Word")

    def _local_wake_word_loop(self):
        """Phase 2 Fix: Korrektes Stream-Cleanup mit try/finally."""
        pa = None
        stream = None
        try:
            import pyaudio
            pa = pyaudio.PyAudio()
            stream = pa.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=8000)
            wake_word = self.cfg.get("wake_word", "jarvis").lower()
            energy_threshold = self.cfg.get("stt_energy_threshold", 500)

            while self._running:
                if self._muted or self._sleeping:
                    time.sleep(0.5)
                    continue
                try:
                    data = stream.read(8000, exception_on_overflow=False)
                except Exception:
                    continue
                energy = self._calculate_energy(data)
                if energy < energy_threshold: 
                    continue
                text = self._recognize_vosk_chunk(data)
                if text and wake_word in text.lower():
                    logger.info(f"🔔 Wake-Word erkannt: '{text}'")
                    self._sleeping = False
                    if self._wake_callback: 
                        self._wake_callback()
                    self._listen_command(stream)
        except Exception as e:
            logger.error(f"Local wake-word error: {e}")
            self._simple_stt_loop()
        finally:
            # Phase 2 Fix: IMMER aufräumen
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            if pa:
                try:
                    pa.terminate()
                except Exception:
                    pass

    def _porcupine_wake_word_loop(self):
        try:
            import pvporcupine
            from pvrecorder import PvRecorder
            access_key = os.environ.get("PORCUPINE_ACCESS_KEY", "")
            if not access_key:
                logger.warning("PORCUPINE_ACCESS_KEY nicht gesetzt")
                self._simple_stt_loop()
                return
            wake_word = self.cfg.get("wake_word", "jarvis").lower()
            builtin = {"jarvis": "jarvis", "computer": "computer", "hey google": "hey google",
                       "alexa": "alexa", "ok google": "ok google", "hey siri": "hey siri"}
            if wake_word in builtin:
                self._porcupine = pvporcupine.create(access_key=access_key, keywords=[builtin[wake_word]])
            else:
                self._porcupine = pvporcupine.create(access_key=access_key, keywords=["jarvis"])
            self._recorder = PvRecorder(frame_length=self._porcupine.frame_length, device_index=-1)
            self._recorder.start()
            while self._running:
                pcm = self._recorder.read()
                if self._porcupine.process(pcm) >= 0:
                    logger.info("🔔 Wake-Word erkannt!")
                    self._sleeping = False
                    if self._wake_callback: 
                        self._wake_callback()
                    self._listen_for_speech(duration=5)
        except Exception as e:
            logger.warning(f"Porcupine nicht verfuegbar: {e}")
            self._simple_stt_loop()

    def _simple_stt_loop(self):
        logger.info("Einfache STT-Schleife")
        while self._running:
            if not self._muted and not self._sleeping:
                self._listen_for_speech(duration=3)
            time.sleep(0.5)

    def _listen_command(self, stream):
        logger.info("Hoere auf Befehl...")
        try:
            frames = []
            for _ in range(20):
                data = stream.read(1600, exception_on_overflow=False)
                frames.append(data)
            audio_data = b"".join(frames)
            text = self._recognize_vosk(audio_data)
            if text:
                logger.info(f"🎤 Befehl erkannt: {text}")
                sleep_word = self.cfg.get("sleep_word", "danke schlaf").lower()
                if sleep_word in text.lower():
                    logger.info("😴 Sleep-Word erkannt")
                    self._sleeping = True
                    return
                if self._callback: 
                    self._callback(text)
        except Exception as e:
            logger.warning(f"Command listen error: {e}")

    def _listen_for_speech(self, duration: int = 5):
        if self._muted: 
            return
        stt_engine = self.cfg.get("stt_engine", "vosk")
        if stt_engine == "none": 
            return
        pa = None
        stream = None
        try:
            import pyaudio
            pa = pyaudio.PyAudio()
            stream = pa.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1600)
            frames = []
            for _ in range(int(duration * 10)):
                data = stream.read(1600, exception_on_overflow=False)
                frames.append(data)
            audio_data = b"".join(frames)
            if stt_engine == "vosk" and self._vosk_model:
                text = self._recognize_vosk(audio_data)
            elif stt_engine == "google":
                text = self._recognize_google(audio_data)
            elif stt_engine == "auto":
                if self._vosk_model: 
                    text = self._recognize_vosk(audio_data)
                else: 
                    text = self._recognize_google(audio_data)
            else: 
                text = None
            if text:
                logger.info(f"🎤 Erkannt: {text}")
                sleep_word = self.cfg.get("sleep_word", "danke schlaf").lower()
                if sleep_word in text.lower():
                    logger.info("😴 Sleep-Word erkannt")
                    self._sleeping = True
                    return
                if self._callback and text.strip(): 
                    self._callback(text)
        except Exception as e:
            logger.warning(f"STT error: {e}")
        finally:
            # Phase 2 Fix: Aufräumen
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            if pa:
                try:
                    pa.terminate()
                except Exception:
                    pass

    def _recognize_vosk(self, audio_data: bytes) -> Optional[str]:
        if not self._vosk_model: 
            return None
        try:
            from vosk import KaldiRecognizer
            import json
            rec = KaldiRecognizer(self._vosk_model, 16000)
            rec.AcceptWaveform(audio_data)
            result = rec.Result()
            data = json.loads(result)
            return data.get("text", "").strip() or None
        except Exception as e:
            logger.warning(f"Vosk error: {e}")
            return None

    def _recognize_vosk_chunk(self, audio_data: bytes) -> Optional[str]:
        return self._recognize_vosk(audio_data)

    def _recognize_google(self, audio_data: bytes) -> Optional[str]:
        try:
            import speech_recognition as sr
            r = sr.Recognizer()
            audio = sr.AudioData(audio_data, 16000, 2)
            return r.recognize_google(audio, language=self.cfg.get("language", "de-DE"))
        except Exception:
            return None

    @staticmethod
    def _calculate_energy(data: bytes) -> float:
        data = data[:len(data) & ~1]
        count = len(data) // 2
        if count == 0: 
            return 0.0
        try:
            format_str = "%dh" % count
            shorts = struct.unpack(format_str, data)
            sum_squares = sum(s * s for s in shorts)
            return math.sqrt(sum_squares / count)
        except struct.error:
            return 0.0
