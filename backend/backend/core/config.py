import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root and backend folder if present
ROOT_DIR = Path(__file__).resolve().parents[3]
BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")
load_dotenv(BACKEND_DIR / ".env")


class Settings:
    def __init__(self):
        self.APP_NAME = os.getenv("APP_NAME", "Insurance Outreach API")
        self.VERSION = os.getenv("VERSION", "0.1.0")

        # Paths
        self.BASE_DIR = BACKEND_DIR
        self.DATA_DIR = Path(os.getenv("DATA_DIR", self.BASE_DIR / "data"))
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.DATA_FILE = Path(os.getenv("DATA_FILE", self.DATA_DIR / "prospects.json"))

        # Email
        self.SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
        self.SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
        self.SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
        self.SENDER_EMAIL = os.getenv("SENDER_EMAIL", self.SMTP_USERNAME)
        self.SENDER_NAME = os.getenv("SENDER_NAME", "Insurance Solutions")

        # Call service
        self.CALL_API_KEY = os.getenv("CALL_API_KEY", "")
        self.CALL_API_URL = os.getenv("CALL_API_URL", "https://api.callservice.com")
        self.CALLER_ID = os.getenv("CALLER_ID", "")


settings = Settings()
