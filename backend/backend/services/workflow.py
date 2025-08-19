from __future__ import annotations

from datetime import datetime
from typing import Optional

from backend.models.domain import (
    Prospect,
    OutreachHistory,
    OutreachChannel,
    OutreachStatus,
)
from backend.services.db import ProspectDatabase
from backend.services.email import EmailService
from backend.services.generator import OutreachGenerator


class OutreachWorkflow:
    def __init__(self, db: Optional[ProspectDatabase] = None,
                 email_service: Optional[EmailService] = None,
                 generator: Optional[OutreachGenerator] = None):
        self.db = db or ProspectDatabase()
        self.email_service = email_service or EmailService()
        self.generator = generator or OutreachGenerator()

    def process_prospect(self, prospect: Prospect) -> None:
        # Generate email content
        subject = self.generator.generate_email_subject(prospect)
        body = self.generator.generate_email_body(prospect)

        # Send email
        sent = self.email_service.send_email(prospect.email, subject, body)
        status = OutreachStatus.SENT if sent else OutreachStatus.FAILED

        # Record history
        history = OutreachHistory(
            prospect_id=prospect.id,
            timestamp=datetime.now(),
            channel=OutreachChannel.EMAIL,
            content={"subject": subject, "body": body},
            status=status,
        )
        self.db.add_history(history)
