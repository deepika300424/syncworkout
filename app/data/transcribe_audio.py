from __future__ import annotations

from pathlib import Path
import sqlite3
import sys

from app.core.settings import get_settings
from app.data.db import connect_db

try:
    from faster_whisper import WhisperModel
except Exception as exc:  # pragma: no cover - optional dependency at runtime
    WhisperModel = None


def _transcribe_file(model: WhisperModel, audio_path: Path) -> str:
    segments, info = model.transcribe(str(audio_path), beam_size=5)
    parts: list[str] = []
    for segment in segments:
        # segment is a dict-like with 'text'
        text = segment.get("text") if isinstance(segment, dict) else getattr(segment, "text", "")
        parts.append(text.strip())
    return " ".join(p for p in parts if p)


def _chunk_text_into_words(text: str, max_words: int = 330) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    i = 0
    while i < len(words):
        chunk_words = words[i : i + max_words]
        chunks.append(" ".join(chunk_words))
        i += max_words
    return chunks


def main() -> int:
    settings = get_settings()
    db = connect_db(settings.sqlite_db_path)
    cursor = db.cursor()
    rows = cursor.execute("SELECT id, exercise_id, cue_index, path FROM audio_cues").fetchall()
    if not rows:
        print("No audio cues found in database.")
        return 0

    # Prepare model
    if WhisperModel is None:
        print("faster_whisper is not available. Install faster-whisper to enable transcription.")
        return 2

    # Choose a small model by default to keep resource use reasonable; users may change.
    print("Loading Whisper model (small) ...")
    model = WhisperModel("small", device="cpu")

    processed = 0
    skipped = 0
    failed = 0

    for row in rows:
        _id, exercise_id, cue_index, audio_path = row
        audio_path = Path(audio_path)
        if not audio_path.exists():
            # try relative to PUMA_DATA_ROOT
            candidate = Path(settings.puma_data_root) / audio_path
            if candidate.exists():
                audio_path = candidate
        if not audio_path.exists():
            print(f"Missing audio file: {audio_path} (db id={_id})")
            failed += 1
            continue

        transcript_path = audio_path.with_suffix(".txt")
        if transcript_path.exists():
            skipped += 1
            # still ensure DB transcript_chunks entries exist? skip for now
            continue

        try:
            print(f"Transcribing: {audio_path} -> {transcript_path}")
            transcript = _transcribe_file(model, audio_path)
            transcript_path.parent.mkdir(parents=True, exist_ok=True)
            transcript_path.write_text(transcript, encoding="utf-8")

            # Chunk transcript into word-based chunks (~330 words ~ 250 tokens)
            chunks = _chunk_text_into_words(transcript, max_words=330)
            # find related workout/section metadata
            exercise_meta = cursor.execute(
                "SELECT workout_id, section_id FROM exercises WHERE exercise_id = ?",
                (exercise_id,),
            ).fetchone()
            workout_id = exercise_meta[0] if exercise_meta else None
            section_id = exercise_meta[1] if exercise_meta else None

            for idx, chunk_text in enumerate(chunks, start=1):
                chunk_filename = transcript_path.with_name(transcript_path.stem + f"_chunk{idx}.txt")
                chunk_filename.write_text(chunk_text, encoding="utf-8")
                chunk_id = f"audio::{exercise_id}::{cue_index}::{idx}"
                cursor.execute(
                    "INSERT OR REPLACE INTO transcript_chunks(chunk_id, exercise_id, workout_id, section_id, chunk_index, start_time, end_time, path, text) VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        chunk_id,
                        exercise_id,
                        workout_id,
                        section_id,
                        idx,
                        None,
                        None,
                        str(chunk_filename),
                        chunk_text,
                    ),
                )

            db.commit()
            processed += 1
        except Exception as exc:
            print(f"Failed: {audio_path}: {exc}")
            failed += 1

    print(f"Done. processed={processed}, skipped={skipped}, failed={failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
