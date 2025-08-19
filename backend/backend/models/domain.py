from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field, field_serializer
from pydantic.config import ConfigDict


class IndustryType(str, Enum):
    TECH = "tech"
    FINANCE = "finance"
    HEALTHCARE = "healthcare"
    RETAIL = "retail"
    MANUFACTURING = "manufacturing"
    EDUCATION = "education"
    CONSTRUCTION = "construction"
    ENERGY = "energy"
    HOSPITALITY = "hospitality"
    TRANSPORTATION = "transportation"


class EngagementLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class OutreachChannel(str, Enum):
    EMAIL = "email"
    CALL = "call"
    BOTH = "both"


class OutreachStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    OPENED = "opened"
    CLICKED = "clicked"
    RESPONDED = "responded"
    FAILED = "failed"


class Prospect(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_name: str
    industry: IndustryType
    contact_name: str
    email: EmailStr
    phone: Optional[str] = None
    engagement_level: EngagementLevel = EngagementLevel.NONE
    notes: str = ""
    last_contact: Optional[datetime] = None
    preferred_channel: OutreachChannel = OutreachChannel.EMAIL
    objections: List[str] = []

    model_config = ConfigDict()

    @field_serializer("last_contact", when_used="json")
    def _serialize_last_contact(self, v: Optional[datetime]) -> Optional[str]:
        return v.isoformat() if v else None


class OutreachHistory(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    prospect_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    channel: OutreachChannel
    content: Dict[str, Any] = {}
    status: OutreachStatus = OutreachStatus.PENDING
    response: Optional[str] = None

    model_config = ConfigDict()

    @field_serializer("timestamp", when_used="json")
    def _serialize_timestamp(self, v: datetime) -> str:
        return v.isoformat()
