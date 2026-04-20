"""
config.py — loads .env and exposes a single cfg singleton.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY:   str = os.getenv("GROQ_API_KEY",   "")
    MODEL:          str = os.getenv("MODEL", "gemini-1.5-flash")
    MAX_PAPERS:     int = int(os.getenv("MAX_PAPERS", "5"))
    OUTPUT_DIR:     str = os.getenv("OUTPUT_DIR", "./output")
    ENABLE_HITL:   bool = os.getenv("ENABLE_HITL", "true").lower() == "true"

    # Which provider to use — detected automatically from which key is set
    @property
    def provider(self) -> str:
        if self.GEMINI_API_KEY and not self.GEMINI_API_KEY.startswith("your_"):
            return "gemini"
        if self.GROQ_API_KEY and not self.GROQ_API_KEY.startswith("your_"):
            return "groq"
        raise EnvironmentError(
            "No API key found.\n"
            "Set GEMINI_API_KEY in .env  →  free at https://aistudio.google.com/app/apikey\n"
            "  OR\n"
            "Set GROQ_API_KEY in .env    →  free at https://console.groq.com"
        )

    def validate(self):
        _ = self.provider  # triggers the error if no key is set


cfg = Config()