from __future__ import annotations

from pathlib import Path

from app.core.settings import get_settings
from app.data.db import connect_db, ingest_manifests, init_db_schema
from app.data.manifest_loader import load_workout_manifests


def main() -> None:
    settings = get_settings()
    manifests = load_workout_manifests(Path(settings.puma_data_root))
    if not manifests:
        raise RuntimeError(f"No manifest files found under: {settings.puma_data_root}")

    connection = connect_db(settings.sqlite_db_path)
    try:
        init_db_schema(connection)
        counts = ingest_manifests(connection, manifests)
    finally:
        connection.close()

    print(
        "Ingestion complete: "
        f"workouts={counts['workouts']}, "
        f"sections={counts['sections']}, "
        f"exercises={counts['exercises']}, "
        f"audio_cues={counts['audio_cues']}"
    )

    # Transcribe audio cues and create transcript chunks so the index can include them
    try:
        from app.data.transcribe_audio import main as transcribe_main

        print("Starting transcription of audio cues (this may take a while)...")
        transcribe_rc = transcribe_main()
        if transcribe_rc == 0:
            print("Transcription step completed.")
        else:
            print(f"Transcription step exited with code: {transcribe_rc}")
    except Exception as exc:
        print(f"Transcription step failed to start: {exc}")


if __name__ == "__main__":
    main()

