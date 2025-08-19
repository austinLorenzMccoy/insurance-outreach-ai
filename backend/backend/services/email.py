from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from backend.core.config import settings


class EmailService:
    def __init__(self,
                 smtp_server: Optional[str] = None,
                 smtp_port: Optional[int] = None,
                 username: Optional[str] = None,
                 password: Optional[str] = None,
                 sender_email: Optional[str] = None,
                 sender_name: Optional[str] = None):
        self.smtp_server = smtp_server or settings.SMTP_SERVER
        self.smtp_port = smtp_port or settings.SMTP_PORT
        self.username = username or settings.SMTP_USERNAME
        self.password = password or settings.SMTP_PASSWORD
        self.sender_email = sender_email or settings.SENDER_EMAIL
        self.sender_name = sender_name or settings.SENDER_NAME

    def send_email(self, to_email: str, subject: str, body: str) -> bool:
        if not self.username or not self.password or not self.sender_email:
            # Missing credentials; treat as dry-run success to avoid runtime errors in dev
            return True

        msg = MIMEMultipart()
        msg["From"] = f"{self.sender_name} <{self.sender_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        try:
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                server.login(self.username, self.password)
                server.send_message(msg)
            return True
        except Exception:
            return False
