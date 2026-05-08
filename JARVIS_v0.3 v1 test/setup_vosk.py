"""Vosk STT Modell automatisch herunterladen."""
import os, urllib.request, zipfile, shutil, sys
from pathlib import Path

def download_file(url, dest, desc=""):
    print(f"  📥 Lade {desc}...")
    try:
        urllib.request.urlretrieve(url, dest)
        print(f"  ✅ {desc} fertig")
        return True
    except Exception as e:
        print(f"  ❌ Fehler bei {desc}: {e}")
        return False

def setup_vosk():
    model_name = "vosk-model-small-de-0.15"
    model_dir = Path("models") / model_name

    if model_dir.exists() and any(model_dir.iterdir()):
        print("[OK] Vosk Modell ist bereits installiert.")
        return 0

    print(f"[INFO] Lade Vosk Modell {model_name}...")
    model_dir.mkdir(parents=True, exist_ok=True)

    url = f"https://alphacephei.com/vosk/models/{model_name}.zip"
    zip_path = Path("models") / f"{model_name}.zip"

    if download_file(url, str(zip_path), f"Vosk {model_name}"):
        print("  📦 Entpacke Vosk...")
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall("models")
        zip_path.unlink(missing_ok=True)
        print("  ✅ Vosk entpackt")

    if model_dir.exists() and any(model_dir.iterdir()):
        print("[OK] ✅ Vosk STT erfolgreich installiert!")
        return 0
    else:
        print("[FEHLER] ❌ Vosk Installation fehlgeschlagen!")
        return 1

if __name__ == "__main__":
    sys.exit(setup_vosk())
