"""Piper TTS Setup — Laedt piper.exe und deutsche Stimmen von HuggingFace.

Korrigierte URLs (Mai 2026):
- Piper Windows Binary: https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip
- Thorsten Medium: https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/de/de_DE/thorsten/medium/
"""
import urllib.request, zipfile, os, shutil
from pathlib import Path

BASE_DIR = Path("models/piper")
BASE_DIR.mkdir(parents=True, exist_ok=True)

PIPER_RELEASE = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip"

# Korrekte HuggingFace URLs fuer deutsche Stimmen
VOICES = {
    "thorsten-de-medium": {
        "onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx",
        "json": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx.json"
    },
    "thorsten-de-low": {
        "onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/de/de_DE/thorsten/low/de_DE-thorsten-low.onnx",
        "json": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/de/de_DE/thorsten/low/de_DE-thorsten-low.onnx.json"
    },
    "eva-de-medium": {
        "onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/de/de_DE/eva_k/medium/de_DE-eva_k-medium.onnx",
        "json": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/de/de_DE/eva_k/medium/de_DE-eva_k-medium.onnx.json"
    }
}

def download(url: str, dest: Path, retries: int = 3):
    """Laedt Datei mit Retry-Logik herunter."""
    for attempt in range(retries):
        try:
            print(f"  📥 Lade {dest.name}... (Versuch {attempt + 1}/{retries})")
            urllib.request.urlretrieve(url, str(dest))
            if dest.stat().st_size > 1000:
                print(f"  ✅ {dest.name} heruntergeladen ({dest.stat().st_size:,} bytes)")
                return True
            else:
                print(f"  ⚠️ Datei zu klein, erneuter Versuch...")
                dest.unlink(missing_ok=True)
        except Exception as e:
            print(f"  ❌ Fehler: {e}")
            if attempt < retries - 1:
                print(f"  🔄 Warte 2 Sekunden...")
                import time
                time.sleep(2)
    return False

def setup_piper_binary():
    """Laedt piper.exe fuer Windows herunter."""
    piper_exe = BASE_DIR / "piper.exe"
    if piper_exe.exists():
        print("[OK] piper.exe bereits vorhanden")
        return True

    zip_path = BASE_DIR / "piper.zip"
    print("[INFO] Lade Piper Windows Binary...")

    if not download(PIPER_RELEASE, zip_path):
        print("[FEHLER] Piper Binary konnte nicht geladen werden!")
        return False

    try:
        print("[INFO] Entpacke piper.zip...")
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(BASE_DIR)
        zip_path.unlink(missing_ok=True)

        # piper.exe finden (kann in Unterordner sein)
        for exe in BASE_DIR.rglob("piper.exe"):
            if exe != piper_exe:
                shutil.copy2(exe, piper_exe)
                print(f"[OK] piper.exe extrahiert nach {piper_exe}")
                return True

        if piper_exe.exists():
            print("[OK] piper.exe bereit")
            return True
        else:
            print("[FEHLER] piper.exe nicht nach Entpacken gefunden!")
            return False
    except Exception as e:
        print(f"[FEHLER] Entpacken fehlgeschlagen: {e}")
        return False

def setup_voice(voice_name: str = "thorsten-de-medium"):
    """Laedt eine Piper-Stimme herunter."""
    if voice_name not in VOICES:
        print(f"[WARNUNG] Unbekannte Stimme: {voice_name}")
        print(f"[INFO] Verfuegbar: {', '.join(VOICES.keys())}")
        voice_name = "thorsten-de-medium"

    urls = VOICES[voice_name]
    onnx_path = BASE_DIR / f"{voice_name}.onnx"
    json_path = BASE_DIR / f"{voice_name}.json"

    success = True

    if not onnx_path.exists():
        if not download(urls["onnx"], onnx_path):
            success = False
    else:
        print(f"[OK] {onnx_path.name} bereits vorhanden")

    if not json_path.exists():
        if not download(urls["json"], json_path):
            success = False
    else:
        print(f"[OK] {json_path.name} bereits vorhanden")

    return success

def main():
    print("=" * 50)
    print("  PIPER TTS SETUP")
    print("=" * 50)
    print()

    # Piper Binary
    binary_ok = setup_piper_binary()

    # Standard-Stimme
    print()
    print("[INFO] Lade Modell thorsten-de-medium...")
    voice_ok = setup_voice("thorsten-de-medium")

    # Pruefung
    print()
    print("=" * 50)
    piper_exe = (BASE_DIR / "piper.exe").exists()
    has_onnx = any(BASE_DIR.glob("*.onnx"))
    has_json = any(BASE_DIR.glob("*.json"))

    print(f"  piper.exe: {'✅' if piper_exe else '❌'}")
    print(f"  *.onnx:    {'✅' if has_onnx else '❌'}")
    print(f"  *.json:    {'✅' if has_json else '❌'}")

    if piper_exe and has_onnx and has_json:
        print()
        print("[OK] ✅ Piper TTS vollstaendig installiert!")
        return 0
    else:
        print()
        print("[FEHLER] ❌ Piper Installation unvollstaendig!")
        if not piper_exe:
            print("  -> piper.exe fehlt")
        if not has_onnx:
            print("  -> .onnx Modell fehlt")
        if not has_json:
            print("  -> .json Config fehlt")
        print("  Fallback zu pyttsx3 wird verwendet.")
        return 1

if __name__ == "__main__":
    exit(main())
