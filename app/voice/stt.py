from __future__ import annotations

from faster_whisper import WhisperModel


class SpeechToText:
    def __init__(self, model_name: str = "base") -> None:
        self._model = WhisperModel(model_name)

    def transcribe_file(self, audio_path: str) -> str:
        segments, _ = self._model.transcribe(audio_path)
        text_parts = [segment.text.strip() for segment in segments if segment.text.strip()]
        return " ".join(text_parts)

