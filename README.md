# imap2webhook

A lightweight Docker service that listens to an IMAP mailbox and forwards new emails to a webhook — built because n8n's native IMAP node is not working like I wish it would. This service handles the listening part and sends a structured payload to any webhook, letting you do whatever you want on the other side.  
  
*soon to be added on nocodenode a lightweight fastAPI to manipulate IMAP*

---

## Behavior

- Email UIDs are recorded on a local SQLite database
- A volume need to be set to store the database file. (otherwise an anonymous volume will be created)

## Webhook Payload

Every new email triggers a POST to your webhook with this JSON body:

```json
{
  "uid": "1809",
  "subject": "Your invoice is ready",
  "from": "billing@example.com",
  "to": "filter@mydomain.com",
  "date": "2025-01-15T14:32:00",
  "text_body": "Please find your invoice...",
  "html_body": "<p>Please find your invoice...</p>",
  "attachments": [
    {
      "filename": "invoice.pdf",
      "content_type": "application/pdf",
      "data": "<base64 encoded content>"
    }
  ]
}
```
## Environment Variables

| Variable      | Required | Default | Description                                         |
|---------------|----------|---------|-----------------------------------------------------|
| `IMAP_HOST`   | yes      | —       | IMAP server hostname                                |
| `IMAP_PORT`   | no       | `993`   | IMAP server port                                    |
| `IMAP_USER`   | yes      | —       | Email address / login                               |
| `IMAP_PWD`    | yes      | —       | Account password                                    |
| `WEBHOOK`     | yes      | —       | URL to POST new emails to                           |
| `MAILBOX`     | no       | `INBOX` | Mailbox/folder to watch                             |
| `PAST_UNSEEN` | no       | `false` | Process unseen emails already in mailbox on startup |
| `ATTACH`      | no       | `true`  | Include attachments as base64 in payload            |
| `FLUSH_DB`    | no       | `false` | If true, flush database at startup                  |
| `LOG_LEVEL`   | no       | `INFO`  | Set the log level                                   |

## Usage

```yaml
services:
  imap2webhook:
    image: nocodenode/imap2webhook:latest
    restart: unless-stopped
    container_name: imap2webhook
    volumes:
      - imap_data:/app/data
    environment:
      IMAP_HOST: mail.emailhost.com
      IMAP_USER: you@yourdomain.com
      IMAP_PWD: yourpassword
      WEBHOOK: https://your-n8n/webhook/xyz
      MAILBOX: INBOX
      PAST_UNSEEN: false
      ATTACH: true
      LOG_LEVEL: INFO
      FLUSH_DB: false
volumes:
  imap_data:

```

```bash
docker compose up -d
docker logs -f imap2webhook
```