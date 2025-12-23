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