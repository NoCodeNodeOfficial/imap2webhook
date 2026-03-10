import logging
import requests
import time
from app.config.settings import settings
from app.imap.client import ImapClient
from app.sqlitedb import SqliteDb

logger = logging.getLogger(__name__)

class EmailManager:
    def __init__(self):
        self.db = SqliteDb("/app/data/data.db")
        self.imap_client = None
        self.first_connect = True

    def run(self):
        if settings.FLUSH_DB:
            logger.warning("Database email uids flushed at startup.")
            self.db.flush_uids()

        if len(self.db.email_uids):
            logger.debug("List of known email uids : %s", self.db.email_uids)

        while True:
            try:
                self.imap_client = ImapClient()
                self.imap_client.connect()
                self.imap_client.select_mailbox(settings.MAILBOX)

                unseens = self.imap_client.fetch_unseen_uids()

                # If PAST_UNSEEN set to True, and first connection, forward all unseen email
                if settings.PAST_UNSEEN and self.first_connect:
                    logger.info("Unseen emails at startup: %s. Forwarding.", len(unseens))
                    self.manage_unseens(unseens)

                # If PAST_UNSEEN set to False, and first connection, register all unseen email to the database
                elif self.first_connect:
                    logger.info("Unseen emails at startup: %s. Watching for new ones only.", len(unseens))
                    for unseen in unseens:
                        # If uid is not already in database
                        if int(unseen.decode()) not in self.db.email_uids:
                            self.db.insert_uid(int(unseen.decode()))
                            logger.info("Registered unseen email: [%s]", int(unseen.decode()))

                # Not a first connection, forward emails that came during a connection error
                else:
                    if unseens:
                        logger.warning("Reconnected. Found %s unseen email(s) during interruption, forwarding.",
                                       len(unseens))
                    self.manage_unseens(unseens)

                self.first_connect = False

                while True:
                    new_email = self.imap_client.idle()
                    if new_email:
                        unseens = self.imap_client.fetch_unseen_uids()
                        self.manage_unseens(unseens)

            except Exception as e:
                logger.error("Connection error: %s. Reconnecting in 10s...", e)
                time.sleep(10)

    def manage_unseens(self, unseens):
        for unseen in unseens:
            # If uid is not already in database
            if int(unseen.decode()) not in self.db.email_uids:
                payload = self.imap_client.parse_email(unseen)
                logger.info("Sending existing unseen email: [%s] : [%s]", int(unseen.decode()), payload.subject)
                self.send_to_webhook(payload)
                self.db.insert_uid(int(unseen.decode()))

    def send_to_webhook(self, payload):
        try:
            response = requests.post(settings.WEBHOOK, json=payload.model_dump(by_alias=True), timeout=10)
            logger.info("Webhook response: %s", response.status_code)
        except Exception as e:
            logger.error("Webhook error: %s", e)
