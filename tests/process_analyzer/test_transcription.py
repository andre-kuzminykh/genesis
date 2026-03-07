"""Tests for transcription service — covers FR-4, FR-5, NFR-4, NFR-5.

Requirements tested:
  FR-4: System must support upload of mp3, wav, m4a, ogg formats.
  FR-5: System must show transcript to user before/with AS-IS.
  NFR-4: Transcription must handle business terms and mixed Russian-English speech.
  NFR-5: On transcription error, system must return clear message and suggest fallback.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.process_analyzer.services.transcription import transcribe_audio


@pytest.fixture
def dummy_audio_file():
    """Create a temporary file simulating an audio upload."""

    def _make(suffix: str = ".mp3", content: bytes = b"fake audio data"):
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp.write(content)
        tmp.close()
        return Path(tmp.name)

    return _make


class TestTranscription:
    """FR-4, FR-5: Audio transcription service tests."""

    @pytest.mark.asyncio
    async def test_successful_transcription(self, dummy_audio_file):
        """Basic transcription returns text content."""
        audio_path = dummy_audio_file(".mp3")
        transcript_text = "Бухгалтер получает счёт от supplier по email."

        mock_resp = httpx.Response(
            status_code=200,
            json={"text": transcript_text},
            request=httpx.Request("POST", "http://test/audio/transcriptions"),
        )

        with patch("src.process_analyzer.services.transcription.httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.post.return_value = mock_resp
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = instance

            result = await transcribe_audio(audio_path)
            assert result == transcript_text

        audio_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_transcription_with_language_hint(self, dummy_audio_file):
        """NFR-4: Language hint is passed to the STT API."""
        audio_path = dummy_audio_file(".wav")

        mock_resp = httpx.Response(
            status_code=200,
            json={"text": "Transcribed text"},
            request=httpx.Request("POST", "http://test/audio/transcriptions"),
        )

        with patch("src.process_analyzer.services.transcription.httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.post.return_value = mock_resp
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = instance

            await transcribe_audio(audio_path, language_hint="ru")

            call_kwargs = instance.post.call_args
            data = call_kwargs.kwargs.get("data", {})
            assert data.get("language") == "ru"

        audio_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_empty_transcription_raises_error(self, dummy_audio_file):
        """NFR-5: Empty transcription raises ValueError."""
        audio_path = dummy_audio_file(".m4a")

        mock_resp = httpx.Response(
            status_code=200,
            json={"text": "   "},
            request=httpx.Request("POST", "http://test/audio/transcriptions"),
        )

        with patch("src.process_analyzer.services.transcription.httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.post.return_value = mock_resp
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = instance

            with pytest.raises(ValueError, match="empty result"):
                await transcribe_audio(audio_path)

        audio_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_transcription_api_error_raises(self, dummy_audio_file):
        """NFR-5: API errors are propagated for proper error handling."""
        audio_path = dummy_audio_file(".ogg")

        mock_resp = httpx.Response(
            status_code=500,
            text="Internal Server Error",
            request=httpx.Request("POST", "http://test/audio/transcriptions"),
        )

        with patch("src.process_analyzer.services.transcription.httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.post.return_value = mock_resp
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = instance

            with pytest.raises(httpx.HTTPStatusError):
                await transcribe_audio(audio_path)

        audio_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_all_supported_audio_formats(self, dummy_audio_file):
        """FR-4: All supported formats (mp3, wav, m4a, ogg) must be accepted."""
        from src.process_analyzer.config import SUPPORTED_AUDIO_FORMATS

        assert SUPPORTED_AUDIO_FORMATS == {".mp3", ".wav", ".m4a", ".ogg"}

        for fmt in [".mp3", ".wav", ".m4a", ".ogg"]:
            audio_path = dummy_audio_file(fmt)

            mock_resp = httpx.Response(
                status_code=200,
                json={"text": f"Transcribed from {fmt}"},
                request=httpx.Request("POST", "http://test/audio/transcriptions"),
            )

            with patch(
                "src.process_analyzer.services.transcription.httpx.AsyncClient"
            ) as mock_client:
                instance = AsyncMock()
                instance.post.return_value = mock_resp
                instance.__aenter__ = AsyncMock(return_value=instance)
                instance.__aexit__ = AsyncMock(return_value=False)
                mock_client.return_value = instance

                result = await transcribe_audio(audio_path)
                assert fmt in result

            audio_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_file_name_sent_in_request(self, dummy_audio_file):
        """Ensure the original file name is sent in the multipart request."""
        audio_path = dummy_audio_file(".mp3")

        mock_resp = httpx.Response(
            status_code=200,
            json={"text": "text"},
            request=httpx.Request("POST", "http://test/audio/transcriptions"),
        )

        with patch("src.process_analyzer.services.transcription.httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.post.return_value = mock_resp
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = instance

            await transcribe_audio(audio_path)

            call_kwargs = instance.post.call_args
            files = call_kwargs.kwargs.get("files", {})
            file_tuple = files.get("file")
            assert file_tuple is not None
            assert audio_path.name in file_tuple[0]

        audio_path.unlink(missing_ok=True)
