"""Echtzeit-Logger mit Datei-Rotation und unbuffered Output fuer Windows CMD."""
import logging, sys, os, threading
from pathlib import Path
from datetime import datetime

class _UnbufferedStream:
    def __init__(self, stream):
        self.stream = stream
    def write(self, data):
        self.stream.write(data)
        self.stream.flush()
    def flush(self):
        self.stream.flush()
    def __getattr__(self, attr):
        return getattr(self.stream, attr)

def _setup_unbuffered():
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(line_buffering=True)
        else:
            sys.stdout = _UnbufferedStream(sys.stdout)
    except Exception:
        try:
            sys.stdout = _UnbufferedStream(sys.stdout)
        except Exception:
            pass

_setup_unbuffered()

class JARVISLogger:
    def __init__(self, name: str = "JARVIS"):
        self.name = name
        self._lock = threading.Lock()
        base = Path(__file__).resolve().parent.parent
        log_dir = base / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = log_dir / f"jarvis_{datetime.now().strftime('%Y%m%d')}.log"
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        if not self.logger.handlers:
            file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter("[%(levelname)s] %(message)s")
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)

    def debug(self, msg: str):
        with self._lock: self.logger.debug(msg)
    def info(self, msg: str):
        with self._lock:
            self.logger.info(msg)
            print(f"[INFO] {msg}", flush=True)
    def warning(self, msg: str):
        with self._lock:
            self.logger.warning(msg)
            print(f"[WARN] {msg}", flush=True)
    def error(self, msg: str):
        with self._lock:
            self.logger.error(msg)
            print(f"[ERROR] {msg}", flush=True)
    def critical(self, msg: str):
        with self._lock:
            self.logger.critical(msg)
            print(f"[CRITICAL] {msg}", flush=True)

_loggers = {}
_lock = threading.Lock()

def get_logger(name: str = "JARVIS") -> JARVISLogger:
    with _lock:
        if name not in _loggers:
            _loggers[name] = JARVISLogger(name)
        return _loggers[name]
