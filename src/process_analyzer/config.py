from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
UPLOAD_DIR = Path(os.getenv("PA_UPLOAD_DIR", "/tmp/process_analyzer_uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


LLM_API_KEY: str = os.getenv("PA_LLM_API_KEY", "")
LLM_BASE_URL: str = os.getenv("PA_LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL: str = os.getenv("PA_LLM_MODEL", "gpt-4o")
LLM_TEMPERATURE: float = float(os.getenv("PA_LLM_TEMPERATURE", "0.3"))
LLM_MAX_TOKENS: int = int(os.getenv("PA_LLM_MAX_TOKENS", "4096"))

STT_API_KEY: str = os.getenv("PA_STT_API_KEY", "") or LLM_API_KEY
STT_BASE_URL: str = os.getenv("PA_STT_BASE_URL", "https://api.openai.com/v1")
STT_MODEL: str = os.getenv("PA_STT_MODEL", "whisper-1")

SUPPORTED_AUDIO_FORMATS = {".mp3", ".wav", ".m4a", ".ogg"}
MAX_AUDIO_SIZE_MB: int = int(os.getenv("PA_MAX_AUDIO_SIZE_MB", "25"))
MAX_TEXT_LENGTH: int = int(os.getenv("PA_MAX_TEXT_LENGTH", "50000"))
