from __future__ import annotations

from google.cloud import texttospeech


class TextToSpeech:
    def __init__(self) -> None:
        self._client = texttospeech.TextToSpeechClient()

    def synthesize_to_mp3(self, text: str, output_path: str) -> str:
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
        )
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
        response = self._client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config,
        )
        with open(output_path, "wb") as handle:
            handle.write(response.audio_content)
        return output_path

