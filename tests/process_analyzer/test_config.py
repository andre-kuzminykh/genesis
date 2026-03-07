"""Tests for configuration module."""

from __future__ import annotations

from pathlib import Path

from src.process_analyzer import config


class TestConfig:
    def test_templates_dir_exists(self):
        assert config.TEMPLATES_DIR.exists()
        assert config.TEMPLATES_DIR.is_dir()

    def test_report_template_exists(self):
        report = config.TEMPLATES_DIR / "report.html"
        assert report.exists()

    def test_supported_audio_formats(self):
        assert ".mp3" in config.SUPPORTED_AUDIO_FORMATS
        assert ".wav" in config.SUPPORTED_AUDIO_FORMATS
        assert ".m4a" in config.SUPPORTED_AUDIO_FORMATS
        assert ".ogg" in config.SUPPORTED_AUDIO_FORMATS

    def test_max_text_length_at_least_20k(self):
        """FR-1: Must support at least 20,000 characters."""
        assert config.MAX_TEXT_LENGTH >= 20_000

    def test_max_audio_size_positive(self):
        assert config.MAX_AUDIO_SIZE_MB > 0

    def test_llm_defaults(self):
        assert config.LLM_BASE_URL
        assert config.LLM_MODEL
        assert 0 <= config.LLM_TEMPERATURE <= 1
        assert config.LLM_MAX_TOKENS > 0

    def test_stt_defaults(self):
        assert config.STT_BASE_URL
        assert config.STT_MODEL

    def test_upload_dir_is_path(self):
        assert isinstance(config.UPLOAD_DIR, Path)
