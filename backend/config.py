import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

class Config:
    ENV = os.getenv("ENV", "dev")

    if ENV == "prod":
        DATABASE_URL = os.getenv(
            "DATABASE_URL",
            "sqlite:////data/theo.db"
        )
    else:
        # local dev default
        data_dir = Path(__file__).resolve().parent.parent / "data"
        data_dir.mkdir(exist_ok=True)
        DATABASE_URL = os.getenv(
            "DATABASE_URL",
            f"sqlite:///{data_dir}/theo.db"
        )

    DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "mock")
    ENABLE_VOICE = os.getenv("ENABLE_VOICE", "true") == "true"

    # Session timeout configuration
    SESSION_EXPIRY_DAYS = int(os.getenv("SESSION_EXPIRY_DAYS", "7"))  # Absolute expiry (default: 7 days)
    DEFAULT_SESSION_INACTIVITY_HOURS = int(os.getenv("DEFAULT_SESSION_INACTIVITY_HOURS", "8"))  # Default inactivity timeout

    # M365 Integration
    M365_CLIENT_ID = os.getenv("M365_CLIENT_ID")
    M365_CLIENT_SECRET = os.getenv("M365_CLIENT_SECRET")
    M365_TENANT_ID = os.getenv("M365_TENANT_ID")