"""Sending email, for the suggestion box (and later sign-in links and
reminders). It uses an SMTP account set in the environment, e.g. a Gmail
address with an app password:

    SMTP_HOST=smtp.gmail.com  SMTP_PORT=587
    SMTP_USER=you@gmail.com   SMTP_PASSWORD=<16-letter app password>
    MAIL_FROM=you@gmail.com   (optional; defaults to SMTP_USER)
    FEEDBACK_TO=where suggestions go (one or more addresses, comma separated)

With nothing set, nothing is sent: suggestions are still saved and listed
in the app for the GM.
"""
import os
import smtplib
import ssl
from email.message import EmailMessage


def configured() -> bool:
    return bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_USER") and os.environ.get("SMTP_PASSWORD"))


def send(to: list[str], subject: str, text: str, attachments: list[tuple[str, str, bytes]] = (), reply_to: str | None = None) -> None:
    """Send one email. attachments: (filename, mime type, bytes). Raises on failure."""
    if not configured():
        raise RuntimeError("Email isn't set up on the server yet")
    msg = EmailMessage()
    msg["From"] = os.environ.get("MAIL_FROM") or os.environ["SMTP_USER"]
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(text)
    for name, mime, data in attachments:
        main, _, sub = mime.partition("/")
        msg.add_attachment(data, maintype=main, subtype=sub or "octet-stream", filename=name)
    host, port = os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "587"))
    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as s:
            s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls(context=ctx)
            s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
            s.send_message(msg)
