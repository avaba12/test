"""Nachrichten-Versand — Email und Telegram.

Phase 2 Fix:
- Einheitliche Timeout-Werte
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from memory.config_manager import ConfigManager
from core.logger import get_logger

logger = get_logger("SendMessage")

def send_message(parameters=None, response=None, player=None, session_memory=None) -> str:
    params = parameters or {}
    to = params.get("to", "").strip()
    message = params.get("message", "").strip()
    msg_type = params.get("type", "auto").lower().strip()
    if not to: 
        return "❌ Kein Empfänger angegeben."
    if not message: 
        return "❌ Keine Nachricht angegeben."

    cfg = ConfigManager()
    if msg_type == "auto":
        msg_type = "email" if "@" in to and "." in to.split("@")[-1] else "whatsapp"

    if msg_type == "email":
        smtp_server = cfg.get("smtp_server", "")
        smtp_port = cfg.get("smtp_port", 587)
        smtp_user = cfg.get("smtp_user", "")
        smtp_pass = cfg.get_api_key("smtp_password")
        from_addr = cfg.get("email_from", smtp_user)
        if not all([smtp_server, smtp_user, smtp_pass]):
            return "❌ SMTP nicht konfiguriert."
        try:
            msg = MIMEMultipart()
            msg["From"] = from_addr
            msg["To"] = to
            msg["Subject"] = params.get("subject", "Nachricht von J.A.R.V.I.S")
            msg.attach(MIMEText(message, "plain", "utf-8"))
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
            server.quit()
            return f"✅ Email an {to} gesendet."
        except Exception as e:
            return f"❌ Email-Fehler: {e}"

    elif msg_type == "whatsapp":
        return f"📱 WhatsApp an {to}: '{message[:50]}...'\nℹ️ Erfordert WhatsApp Business API oder Twilio."

    elif msg_type == "telegram":
        token = cfg.get_api_key("telegram_bot_token")
        if not token: 
            return "❌ Telegram Bot Token nicht konfiguriert."
        try:
            import requests
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            resp = requests.post(url, json={"chat_id": to, "text": message}, timeout=10)
            return f"✅ Telegram an {to} gesendet." if resp.status_code == 200 else f"❌ Telegram-Fehler: {resp.status_code}"
        except requests.exceptions.Timeout:
            return f"⏳ Telegram Timeout."
        except Exception as e:
            return f"❌ Telegram-Fehler: {e}"

    return f"❌ Unbekannter Typ: '{msg_type}'. Verfuegbar: email, whatsapp, telegram"
