@echo off
title J.A.R.V.I.S v3.0
color 0a
cd /d "%~dp0"

echo.
echo ============================================
echo J.A.R.V.I.S v3.0
echo ============================================
echo.

:: Pruefe venv
if not exist "venv\Scripts\activate.bat" (
 echo [FEHLER] Virtuelle Umgebung nicht gefunden!
 echo [INFO] Fuehre zuerst install.bat aus.
 goto ENDE
)

call "venv\Scripts\activate.bat"
if errorlevel 1 (
 echo [FEHLER] venv konnte nicht aktiviert werden!
 goto ENDE
)

set PYTHONUNBUFFERED=1
set PYTHONDONTWRITEBYTECODE=1

:: Pruefe Ollama
echo [INFO] Pruefe Ollama...
python -c "import urllib.request; urllib.request.urlopen('http://localhost:11434', timeout=3)" >nul 2>&1
if errorlevel 1 (
 echo [WARNUNG] Ollama laeuft nicht!
 echo Bitte starte Ollama: https://ollama.com
 echo Im Terminal: ollama serve
 echo.
) else (
 echo [OK] Ollama verbunden
)

:: Pruefe Piper
echo [INFO] Pruefe Piper TTS...
python -c "import os; from pathlib import Path; b=Path('models/piper'); ex=(b/'piper.exe').exists(); mo=any(b.glob('*.onnx')); js=any(b.glob('*.json')); exit(0 if (ex and mo and js) else 1)" >nul 2>&1
if errorlevel 1 (
 echo [INFO] Piper wird installiert...
 python "setup_piper.py"
) else (
 echo [OK] Piper TTS bereit
)

:: Pruefe Vosk
echo [INFO] Pruefe Vosk STT...
if exist "models\vosk-model-small-de-0.15\am\final.mdl" (
 echo [OK] Vosk STT bereit
) else (
 echo [INFO] Vosk wird installiert...
 python "setup_vosk.py"
)

:: Pruefe pydub
echo [INFO] Pruefe pydub...
python -c "import pydub" >nul 2>&1
if errorlevel 1 (
 echo [INFO] pydub wird nachinstalliert...
 pip install pydub
) else (
 echo [OK] pydub bereit
)

:: Pruefe Config
if not exist "config\settings.json" (
 echo [INFO] Erstelle Default-Konfiguration...
 if not exist "config" mkdir "config"
 python -c "import json; open('config/settings.json','w').write(json.dumps({'user_name':'Sir','language':'de-DE','theme':'dark','tts_engine':'piper','tts_voice':'thorsten-de-medium','tts_speed':1.0,'tts_volume':0.9,'stt_engine':'vosk','wake_word':'jarvis','sleep_word':'danke schlaf','ollama_host':'http://localhost:11434','chat_model':'llama3','code_model':'codellama','vision_model':'llava','temperature':0.7,'top_p':0.9,'memory_limit':1000,'auto_cleanup':True,'pin_enabled':False,'pin_code':'','session_timeout':30,'confirmation_required':True,'offline_mode':True,'use_local_wake_word':True,'show_thinking':False,'thinking_mode':'instant','allowed_apps':['notepad','chrome','vscode','explorer','cmd','spotify','discord'],'allowed_urls':[],'skills':{'web_search':True,'file_access':True,'comfyui':False,'pc_control':True,'plugins':True,'telegram':False,'discord':False,'home_assistant':False,'obsidian':False,'voice_control':True,'rag':True},'master_mode':'standard','comfyui_url':'http://127.0.0.1:8188','comfyui_output_dir':'outputs/comfyui','rocm_path':'C:/Program Files/AMD/ROCm/6.1/bin','piper_model':'thorsten-de-medium','piper_path':'models/piper','vosk_model':'vosk-model-small-de-0.15'},indent=4))"
)

if not exist "config\api_keys.json" (
 python -c "import json; open('config/api_keys.json','w').write(json.dumps({'gemini_api_key':'','telegram_bot_token':'','discord_webhook':'','home_assistant_url':'','home_assistant_token':'','smtp_server':'','smtp_port':587,'smtp_user':'','smtp_password':'','email_from':''},indent=4))"
)

:: Pruefe .env
if not exist ".env" (
 if exist ".env.example" (
  echo.
  echo [INFO] .env nicht gefunden — .env.example liegt bereit.
  echo [INFO] Kopiere .env.example nach .env und fuelle deine API-Keys ein.
  echo.
 )
)

:: Zeige Config
echo.
echo [INFO] Aktuelle Konfiguration:
python -c "import json; c=json.load(open('config/settings.json')); print(' User:', c.get('user_name','Sir')); print(' TTS:', c.get('tts_engine','piper')); print(' Offline:', c.get('offline_mode',True)); print(' Wake-Word:', c.get('wake_word','jarvis')); print(' ComfyUI:', c.get('comfyui_url',''))"
echo.

:: Starte
echo ============================================
echo Starte J.A.R.V.I.S...
echo ============================================
echo [INFO] Alle Logs erscheinen hier in ECHTZEIT:
echo.

python -u "main.py"

echo.
echo ============================================
echo J.A.R.V.I.S wurde beendet.
echo ============================================

:ENDE
echo.
echo ============================================
echo Fenster bleibt offen. Druecke eine Taste zum Schliessen.
echo ============================================
pause >nul
