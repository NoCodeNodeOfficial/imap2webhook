import os
import logging
import sys

logger = logging.getLogger(__name__)

class Settings:
    IMAP_HOST: str
    IMAP_PORT: int
    IMAP_USER: str
    IMAP_PWD:  str
    API_KEY:   str
    LOG_LEVEL: str

    def __init__(self):
        self.IMAP_HOST      = os.environ.get("IMAP_HOST", "")
        self.IMAP_PORT      = int(os.environ.get("IMAP_PORT", "993"))
        self.IMAP_USER      = os.environ.get("IMAP_USER", "")
        self.IMAP_PWD       = os.environ.get("IMAP_PWD",  "")
        self.WEBHOOK        = os.environ.get("WEBHOOK",   "")
        self.MAILBOX        = os.environ.get("MAILBOX", "INBOX")
        self.PAST_UNSEEN    = os.environ.get("PAST_UNSEEN", "false").lower() == "true"
        self.ATTACH         = os.environ.get("ATTACH", "true").lower() == "true"
        self.FLUSH_DB       = os.environ.get("FLUSH_DB", "false").lower() == "true"
        self.LOG_LEVEL      = os.environ.get("LOG_LEVEL", "INFO").upper()
        self._validate()

    def _validate(self):
        mandatory = {
            "IMAP_HOST": self.IMAP_HOST,
            "IMAP_USER": self.IMAP_USER,
            "IMAP_PWD":  self.IMAP_PWD,
            "WEBHOOK":   self.WEBHOOK,
        }
        missing = [name for name, val in mandatory.items() if not val]
        if missing:
            logger.error(
                "Missing mandatory environment variables: %s — fix your config and restart the container.",
                ', '.join(missing)
            )
            sys.exit(1)

settings = Settings()
