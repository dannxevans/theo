import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    ENV = os.getenv("ENV", "dev")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////data/theo.db")
    DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "mock")
    ENABLE_VOICE = os.getenv("ENABLE_VOICE", "true") == "true"  