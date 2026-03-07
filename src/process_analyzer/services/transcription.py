from __future__ import annotations

import logging
from pathlib import Path

import httpx

from src.process_analyzer import config

logger = logging.getLogger(__name__)


async def transcribe_audio(audio_path: Path, language_hint: str | None = None) -> str:
    headers = {
        "Authorization": f"Bearer {config.STT_API_KEY}",
    }

    with open(audio_path, "rb") as f:
        files = {"file": (audio_path.name, f, "application/octet-stream")}
        data: dict[str, str] = {"model": config.STT_MODEL}
        if language_hint:
            data["language"] = language_hint

        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{config.STT_BASE_URL}/audio/transcriptions",
                headers=headers,
                files=files,
                data=data,
            )
            resp.raise_for_status()
            result = resp.json()

    transcript: str = result.get("text", "")
    if not transcript.strip():
        raise ValueError("Transcription returned empty result")

    logger.info("Transcription complete: %d characters", len(transcript))
    return transcript
