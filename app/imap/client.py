import base64
import imaplib
import logging
import email
from app.config.settings import settings
from app.imap.schemas import MessageEnvelope, Attachment

logger = logging.getLogger(__name__)

class ImapClient:
    """
    Thin wrapper around imaplib.IMAP4_SSL.
    Handles connection, login, and reconnection.
    Use as a context manager : with ImapClient() as client:
    """

    def __init__(self):
        self._conn: imaplib.IMAP4_SSL | None = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self) -> None:
        logger.debug("Opening IMAP connection to %s:%s", settings.IMAP_HOST, settings.IMAP_PORT)
        self._conn = imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT)
        self._conn.login(settings.IMAP_USER, settings.IMAP_PWD)
        logger.debug("IMAP login successful for %s", settings.IMAP_USER)

    def disconnect(self) -> None:
        if self._conn:
            try:
                self._conn.logout()
                logger.debug("IMAP connection closed cleanly")
            except Exception:
                logger.debug("IMAP connection closed with error (ignored)")
            finally:
                self._conn = None

    # ------------------------------------------------------------------
    # Mailbox helpers
    # ------------------------------------------------------------------

    def select_mailbox(self, mailbox: str = "INBOX") -> int:
        """Selects a mailbox and returns the message count."""
        status, data = self._conn.select(mailbox)
        if status != "OK":
            raise ValueError(f"Cannot select mailbox '{mailbox}': {data}")
        count = int(data[0])
        logger.debug("Selected mailbox '%s' (%d messages)", mailbox, count)
        return count

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------
    def fetch_unseen_uids(self):
        _, data = self._conn.uid("search", None, "UNSEEN")
        return set(data[0].split())


    def parse_email(self, uid: str) -> MessageEnvelope:
        status, data = self._conn.uid("fetch", uid, "(RFC822)")
        if status != "OK" or not data or data[0] is None:
            raise ValueError(f"UID {uid} not found in '{settings.MAILBOX}'")

        msg = email.message_from_bytes(data[0][1])
        payload = MessageEnvelope(uid=uid)
        payload.subject = msg.get("Subject", "")
        payload.from_ = msg.get("From", "")
        payload.to = msg.get("To", "")
        payload.date = msg.get("Date", "")

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = part.get_content_disposition()
                filename = part.get_filename()

                if filename or content_disposition == "attachment":
                    if settings.ATTACH:
                        attachment_file = Attachment(
                            filename=filename or "unnamed",
                            content_type=content_type,
                            data=base64.b64encode(part.get_payload(decode=True)).decode()
                        )
                        payload.attachments.append(attachment_file)
                elif content_type == "text/plain":
                    payload.text_body += part.get_payload(decode=True).decode(errors="replace")
                elif content_type == "text/html":
                    payload.html_body += part.get_payload(decode=True).decode(errors="replace")
        else:
            content_type = msg.get_content_type()
            if content_type == "text/plain":
                payload.text_body = msg.get_payload(decode=True).decode(errors="replace")
            elif content_type == "text/html":
                payload.html_body = msg.get_payload(decode=True).decode(errors="replace")

        return payload

    # ------------------------------------------------------------------
    # Idle
    # ------------------------------------------------------------------
    def idle(self):
        logger.debug("Starting IDLE...")
        self._conn.send(b"A001 IDLE\r\n")

        response = self._conn.readline()
        logger.debug("IDLE confirm: %s", response)
        if not response.startswith(b"+"):
            raise RuntimeError(f"Server rejected IDLE: {response}")

        self._conn.socket().settimeout(29 * 60)

        try:
            while True:
                line = self._conn.readline()
                if not line:
                    raise ConnectionError("Server closed the connection")
                logger.debug("IDLE line: %s", line)
                if b"EXISTS" in line:
                    logger.info("New email detected.")
                    self._conn.send(b"DONE\r\n")
                    # Drain the IDLE completion response before issuing new commands
                    while True:
                        line = self._conn.readline()
                        if not line:
                            raise ConnectionError("Server closed the connection")
                        if b"OK" in line or b"NO" in line or b"BAD" in line:
                            break
                    return True
        except Exception as e:
            logger.warning("IDLE interrupted: %s", e)
            return False