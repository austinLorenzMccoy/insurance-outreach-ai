from __future__ import annotations

from textwrap import dedent
from backend.models.domain import Prospect, IndustryType


class OutreachGenerator:
    def generate_email_subject(self, prospect: Prospect) -> str:
        return f"Insurance solutions for {prospect.company_name}"

    def generate_email_body(self, prospect: Prospect) -> str:
        industry_tip = {
            IndustryType.TECH: "Tech companies face unique cybersecurity and IP risks.",
            IndustryType.FINANCE: "Compliance and fraud protection are critical in finance.",
            IndustryType.RETAIL: "Retail needs inventory and liability protection across channels.",
        }.get(prospect.industry, "Let's tailor coverage to your industry needs.")

        body = f"""
        Hi {prospect.contact_name},
        
        I'm an insurance consultant specializing in {prospect.industry.value}.
        {industry_tip}
        
        I'd love to share a brief plan to optimize coverage for {prospect.company_name} while managing costs.
        
        Best,
        {"Insurance Solutions"}
        """
        return dedent(body).strip()

    def generate_call_script(self, prospect: Prospect) -> dict:
        return {
            "introduction": f"Hi {prospect.contact_name}, this is from Insurance Solutions."
                             f" I help {prospect.industry.value} companies like {prospect.company_name} manage risk.",
            "key_points": [
                "Brief risk overview tailored to their industry",
                "How coverage aligns to business goals",
                "Next steps and quick time to value",
            ],
            "questions": [
                "What are your top risk concerns this quarter?",
                "Any upcoming changes (hiring, expansion, product)?",
            ],
            "close": "Would next Tuesday or Wednesday work for a 15-minute call?",
        }
