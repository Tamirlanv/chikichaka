from __future__ import annotations

from types import SimpleNamespace

import pytest

from invision_api.services.video_processing.transcription_openai import (
    ASRConfigError,
    ASRNetworkError,
    transcribe_audio_wav,
)


def test_transcribe_uses_dedicated_asr_config(monkeypatch, tmp_path) -> None:
    wav = tmp_path / "audio.wav"
    wav.write_bytes(b"fake-wav")

    monkeypatch.setattr(
        "invision_api.services.video_processing.transcription_openai.get_settings",
        lambda: SimpleNamespace(
            asr_api_key="asr-key",
            openai_api_key="legacy-key",
            asr_base_url="https://asr.example.com/v1",
            asr_model="whisper-1",
            asr_timeout_seconds=17.0,
        ),
    )

    captured: dict[str, object] = {}

    class _FakeClient:
        def __init__(self, *, api_key: str, base_url: str) -> None:
            captured["api_key"] = api_key
            captured["base_url"] = base_url
            self.audio = SimpleNamespace(
                transcriptions=SimpleNamespace(create=self._create),
            )

        def _create(self, **kwargs):
            captured["request"] = kwargs
            return SimpleNamespace(text="Пример транскрипта")

    monkeypatch.setattr("invision_api.services.video_processing.transcription_openai.OpenAI", _FakeClient)

    text, conf = transcribe_audio_wav(wav)
    assert text == "Пример транскрипта"
    assert conf is None
    assert captured["api_key"] == "asr-key"
    assert captured["base_url"] == "https://asr.example.com/v1"
    req = captured["request"]
    assert isinstance(req, dict)
    assert req["model"] == "whisper-1"
    assert req["language"] == "ru"
    assert req["timeout"] == 17.0


def test_transcribe_uses_openai_key_fallback(monkeypatch, tmp_path) -> None:
    wav = tmp_path / "audio.wav"
    wav.write_bytes(b"fake-wav")
    monkeypatch.setattr(
        "invision_api.services.video_processing.transcription_openai.get_settings",
        lambda: SimpleNamespace(
            asr_api_key=None,
            openai_api_key="legacy-key",
            asr_base_url="https://api.openai.com/v1",
            asr_model="whisper-1",
            asr_timeout_seconds=20.0,
        ),
    )

    class _FakeClient:
        def __init__(self, *, api_key: str, base_url: str) -> None:
            assert api_key == "legacy-key"
            assert base_url == "https://api.openai.com/v1"
            self.audio = SimpleNamespace(transcriptions=SimpleNamespace(create=lambda **_kw: SimpleNamespace(text="ok")))

    monkeypatch.setattr("invision_api.services.video_processing.transcription_openai.OpenAI", _FakeClient)
    text, _ = transcribe_audio_wav(wav)
    assert text == "ok"


def test_transcribe_raises_config_error_without_keys(monkeypatch, tmp_path) -> None:
    wav = tmp_path / "audio.wav"
    wav.write_bytes(b"fake-wav")
    monkeypatch.setattr(
        "invision_api.services.video_processing.transcription_openai.get_settings",
        lambda: SimpleNamespace(
            asr_api_key=None,
            openai_api_key=None,
            asr_base_url="https://api.openai.com/v1",
            asr_model="whisper-1",
            asr_timeout_seconds=10.0,
        ),
    )

    with pytest.raises(ASRConfigError):
        transcribe_audio_wav(wav)


def test_transcribe_maps_timeout_to_network_error(monkeypatch, tmp_path) -> None:
    wav = tmp_path / "audio.wav"
    wav.write_bytes(b"fake-wav")
    monkeypatch.setattr(
        "invision_api.services.video_processing.transcription_openai.get_settings",
        lambda: SimpleNamespace(
            asr_api_key="asr-key",
            openai_api_key=None,
            asr_base_url="https://asr.example.com/v1",
            asr_model="whisper-1",
            asr_timeout_seconds=10.0,
        ),
    )

    class _FakeTimeout(Exception):
        pass

    monkeypatch.setattr("invision_api.services.video_processing.transcription_openai.APITimeoutError", _FakeTimeout)

    class _FakeClient:
        def __init__(self, *, api_key: str, base_url: str) -> None:
            _ = (api_key, base_url)
            self.audio = SimpleNamespace(transcriptions=SimpleNamespace(create=self._create))

        @staticmethod
        def _create(**_kwargs):
            raise _FakeTimeout("timeout")

    monkeypatch.setattr("invision_api.services.video_processing.transcription_openai.OpenAI", _FakeClient)

    with pytest.raises(ASRNetworkError):
        transcribe_audio_wav(wav)
