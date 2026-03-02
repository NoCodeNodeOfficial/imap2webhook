import imaplib
import email
import os
import time
import requests
import base64
import sys
import logging

# --- Env vars ---
IMAP_HOST   = os.environ["IMAP_HOST"]
IMAP_USER   = os.environ["IMAP_USER"]
IMAP_PWD    = os.environ["IMAP_PWD"]
WEBHOOK     = os.environ["WEBHOOK"]
MAILBOX     = os.environ.get("MAILBOX", "INBOX")
PAST_UNSEEN = os.environ.get("PAST_UNSEEN", "false").lower() == "true"
ATTACH      = os.environ.get("ATTACH", "true").lower() == "true"
LOG_LEVEL   = os.environ.get("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Validate mandatory env vars
missing = [name for name, val in {
    "IMAP_HOST": IMAP_HOST,
    "IMAP_USER": IMAP_USER,
    "IMAP_PWD":  IMAP_PWD,
    "WEBHOOK":   WEBHOOK,
}.items() if not val]

if missing:
    logger.error("Missing mandatory environment variable(s): %s", ', '.join(missing))
    sys.exit(1)

# --- Connect ---
def connect():
    logger.debug("Connecting to IMAP...")
    mail = imaplib.IMAP4_SSL(IMAP_HOST)
    mail.login(IMAP_USER, IMAP_PWD)
    mail.select(MAILBOX)
    logger.info("Connected to %s", MAILBOX)
    return mail

# --- Fetch unseen UIDs ---
def fetch_unseen_uids(mail):
    _, data = mail.search(None, "UNSEEN")
    uids = set(data[0].split())
    return uids

# --- Parse email ---
def parse_email(mail, uid):
    _, data = mail.fetch(uid, "(RFC822)")
    raw = data[0][1]
    msg = email.message_from_bytes(raw)

    payload = {
        "uid": uid.decode(),
        "subject": msg.get("Subject", ""),
        "from": msg.get("From", ""),
        "to": msg.get("To", ""),
        "date": msg.get("Date", ""),
        "body_text": "",
        "body_html": "",
        "attachments": [],
    }
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = part.get_content_disposition()
            filename = part.get_filename()

            if filename or content_disposition == "attachment":
                if ATTACH:
                    payload["attachments"].append({
                        "filename": filename or "unnamed",
                        "content_type": content_type,
                        "data": base64.b64encode(part.get_payload(decode=True)).decode(),
                    })
            elif content_type == "text/plain":
                payload["body_text"] += part.get_payload(decode=True).decode(errors="replace")
            elif content_type == "text/html":
                payload["body_html"] += part.get_payload(decode=True).decode(errors="replace")
    else:
        content_type = msg.get_content_type()
        if content_type == "text/plain":
            payload["body_text"] = msg.get_payload(decode=True).decode(errors="replace")
        elif content_type == "text/html":
            payload["body_html"] = msg.get_payload(decode=True).decode(errors="replace")

    return payload

# --- Send to webhook ---
def send_to_webhook(payload):
    try:
        response = requests.post(WEBHOOK, json=payload, timeout=10)
        logger.info("Webhook response: %s", response.status_code)
    except Exception as e:
        logger.error("Webhook error: %s", e)

# --- IDLE ---
def idle(mail):
    logger.debug("Starting IDLE...")
    mail.send(b"A001 IDLE\r\n")

    response = mail.readline()
    logger.debug("IDLE confirm: %s", response)
    if not response.startswith(b"+"):
        raise RuntimeError(f"Server rejected IDLE: {response}")

    mail.socket().settimeout(29 * 60)

    try:
        while True:
            line = mail.readline()
            if not line:
                raise ConnectionError("Server closed the connection")
            logger.debug("IDLE line: %s", line)
            if b"EXISTS" in line:
                logger.info("New email detected.")
                mail.send(b"DONE\r\n")
                # Drain the IDLE completion response before issuing new commands
                while True:
                    line = mail.readline()
                    if not line:
                        raise ConnectionError("Server closed the connection")
                    if b"OK" in line or b"NO" in line or b"BAD" in line:
                        break
                return True
    except Exception as e:
        logger.warning("IDLE interrupted: %s", e)
        return False

# --- Main loop ---
def run():
    first_connect = True
    while True:
        try:
            mail = connect()
            processed_uids = set()
            uids = fetch_unseen_uids(mail)

            if PAST_UNSEEN and first_connect:
                # Send all existing unseen on first startup
                for uid in uids:
                    payload = parse_email(mail, uid)
                    logger.info("Sending existing unseen email: %n", payload['subject'])
                    send_to_webhook(payload)
                    processed_uids.add(uid)
            elif first_connect:
                # Mark current unseen as already processed at startup when PAST_UNSEEN is disable
                processed_uids = uids.copy()
                logger.info("Unseen emails at startup: %s. Watching for new ones only.", len(uids))
            else:
                # Reconnect after interruption — forward anything unseen we haven't seen before
                if uids:
                    logger.warning("Reconnected. Found %s unseen email(s) during interruption, forwarding.", len(uids))
                for uid in uids:
                    payload = parse_email(mail, uid)
                    send_to_webhook(payload)

            first_connect = False

            while True:
                got_new = idle(mail)
                if got_new:
                    uids = fetch_unseen_uids(mail)
                    new_uids = uids - processed_uids
                    for uid in new_uids:
                        payload = parse_email(mail, uid)
                        logger.info("Forwarding new email: %s", payload['subject'])
                        send_to_webhook(payload)
                        processed_uids.add(uid)

        except Exception as e:
            logger.error("Connection error: %s. Reconnecting in 10s...", e)
            time.sleep(10)

if __name__ == "__main__":
    run()
