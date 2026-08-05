from __future__ import annotations

import sqlite3
from pathlib import Path

from app.core.schemas import RetrievalChunk, WorkoutManifest


def connect_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path))
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def init_db_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS workouts (
          workout_id TEXT PRIMARY KEY,
          title TEXT NOT NULL,
          local_cover TEXT NOT NULL,
          local_intro TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sections (
          section_id TEXT PRIMARY KEY,
          workout_id TEXT NOT NULL,
          title TEXT NOT NULL,
          FOREIGN KEY(workout_id) REFERENCES workouts(workout_id)
        );

        CREATE TABLE IF NOT EXISTS exercises (
          exercise_id TEXT PRIMARY KEY,
          section_id TEXT NOT NULL,
          workout_id TEXT NOT NULL,
          title TEXT NOT NULL,
          local_video TEXT NOT NULL,
          local_preview TEXT NOT NULL,
          local_image TEXT NOT NULL,
          FOREIGN KEY(section_id) REFERENCES sections(section_id),
          FOREIGN KEY(workout_id) REFERENCES workouts(workout_id)
        );

        CREATE TABLE IF NOT EXISTS audio_cues (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          exercise_id TEXT NOT NULL,
          cue_index INTEGER NOT NULL,
          path TEXT NOT NULL,
          FOREIGN KEY(exercise_id) REFERENCES exercises(exercise_id),
          UNIQUE(exercise_id, cue_index)
        );

        CREATE TABLE IF NOT EXISTS transcript_chunks (
          chunk_id TEXT PRIMARY KEY,
          exercise_id TEXT NOT NULL,
          workout_id TEXT,
          section_id TEXT,
          chunk_index INTEGER NOT NULL,
          start_time REAL,
          end_time REAL,
          path TEXT,
          text TEXT,
          FOREIGN KEY(exercise_id) REFERENCES exercises(exercise_id)
        );
        """
    )
    connection.commit()


def ingest_manifests(connection: sqlite3.Connection, manifests: list[WorkoutManifest]) -> dict[str, int]:
    workout_count = 0
    section_count = 0
    exercise_count = 0
    cue_count = 0

    for workout in manifests:
        connection.execute(
            """
            INSERT INTO workouts(workout_id, title, local_cover, local_intro)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(workout_id) DO UPDATE SET
              title=excluded.title,
              local_cover=excluded.local_cover,
              local_intro=excluded.local_intro
            """,
            (workout.workout_id, workout.title, workout.local_cover, workout.local_intro),
        )
        workout_count += 1

        for section in workout.sections:
            connection.execute(
                """
                INSERT INTO sections(section_id, workout_id, title)
                VALUES(?, ?, ?)
                ON CONFLICT(section_id) DO UPDATE SET
                  workout_id=excluded.workout_id,
                  title=excluded.title
                """,
                (section.section_id, workout.workout_id, section.title),
            )
            section_count += 1

            for exercise in section.exercises:
                connection.execute(
                    """
                    INSERT INTO exercises(
                      exercise_id, section_id, workout_id, title, local_video, local_preview, local_image
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(exercise_id) DO UPDATE SET
                      section_id=excluded.section_id,
                      workout_id=excluded.workout_id,
                      title=excluded.title,
                      local_video=excluded.local_video,
                      local_preview=excluded.local_preview,
                      local_image=excluded.local_image
                    """,
                    (
                        exercise.exercise_id,
                        section.section_id,
                        workout.workout_id,
                        exercise.title,
                        exercise.local_video or "",
                        exercise.local_preview or "",
                        exercise.local_image or "",
                    ),
                )
                exercise_count += 1

                cue_paths = [cue for cue in (exercise.local_audio_cues or []) if cue]
                for cue_index, cue_path in enumerate(cue_paths, start=1):
                    connection.execute(
                        """
                        INSERT INTO audio_cues(exercise_id, cue_index, path)
                        VALUES(?, ?, ?)
                        ON CONFLICT(exercise_id, cue_index) DO UPDATE SET
                          path=excluded.path
                        """,
                        (exercise.exercise_id, cue_index, cue_path),
                    )
                    cue_count += 1

    connection.commit()
    return {
        "workouts": workout_count,
        "sections": section_count,
        "exercises": exercise_count,
        "audio_cues": cue_count,
    }


def has_workout_data(connection: sqlite3.Connection) -> bool:
    result = connection.execute("SELECT COUNT(*) FROM workouts").fetchone()
    if result is None:
        raise RuntimeError("Failed to check workouts table row count.")
    return int(result[0]) > 0


def load_chunks_from_db(connection: sqlite3.Connection) -> list[RetrievalChunk]:
    chunks: list[RetrievalChunk] = []

    workout_rows = connection.execute(
        "SELECT workout_id, title, local_intro, local_cover FROM workouts ORDER BY title"
    ).fetchall()
    for workout_id, title, local_intro, local_cover in workout_rows:
        chunks.append(
            RetrievalChunk(
                chunk_id=f"workout::{workout_id}",
                text=(
                    f"Workout title: {title}. "
                    f"Workout ID: {workout_id}. "
                    f"Intro video: {local_intro}. "
                    f"Cover image: {local_cover}."
                ),
                metadata={
                    "entity_type": "workout",
                    "workout_id": workout_id,
                    "workout_title": title,
                    "local_intro": local_intro,
                    "local_cover": local_cover,
                },
            )
        )

    section_rows = connection.execute(
        """
        SELECT s.section_id, s.title, w.workout_id, w.title
        FROM sections s
        JOIN workouts w ON w.workout_id = s.workout_id
        ORDER BY w.title, s.title
        """
    ).fetchall()
    for section_id, section_title, workout_id, workout_title in section_rows:
        chunks.append(
            RetrievalChunk(
                chunk_id=f"section::{section_id}",
                text=(
                    f"Section title: {section_title}. "
                    f"Section ID: {section_id}. "
                    f"Workout title: {workout_title}. "
                    f"Workout ID: {workout_id}."
                ),
                metadata={
                    "entity_type": "section",
                    "workout_id": workout_id,
                    "workout_title": workout_title,
                    "section_id": section_id,
                    "section_title": section_title,
                },
            )
        )

    exercise_rows = connection.execute(
        """
        SELECT e.exercise_id, e.title, e.local_video, e.local_preview, e.local_image,
               s.section_id, s.title, w.workout_id, w.title
        FROM exercises e
        JOIN sections s ON s.section_id = e.section_id
        JOIN workouts w ON w.workout_id = e.workout_id
        ORDER BY w.title, s.title, e.title
        """
    ).fetchall()
    for (
        exercise_id,
        exercise_title,
        local_video,
        local_preview,
        local_image,
        section_id,
        section_title,
        workout_id,
        workout_title,
    ) in exercise_rows:
        cue_rows = connection.execute(
            """
            SELECT path FROM audio_cues
            WHERE exercise_id = ?
            ORDER BY cue_index
            """,
            (exercise_id,),
        ).fetchall()
        cue_paths = [row[0] for row in cue_rows]
        chunks.append(
            RetrievalChunk(
                chunk_id=f"exercise::{exercise_id}",
                text=(
                    f"Exercise title: {exercise_title}. "
                    f"Exercise ID: {exercise_id}. "
                    f"Section title: {section_title}. "
                    f"Section ID: {section_id}. "
                    f"Workout title: {workout_title}. "
                    f"Workout ID: {workout_id}. "
                    f"Video: {local_video or ''}. "
                    f"Preview: {local_preview or ''}. "
                    f"Image: {local_image or ''}."
                ),
                metadata={
                    "entity_type": "exercise",
                    "workout_id": workout_id,
                    "workout_title": workout_title,
                    "section_id": section_id,
                    "section_title": section_title,
                    "exercise_id": exercise_id,
                    "exercise_title": exercise_title,
                    "local_video": local_video or "",
                    "local_preview": local_preview or "",
                    "local_image": local_image or "",
                    "local_audio_cues": "|".join(cue_paths),
                },
            )
        )

        # Add audio transcript chunks (if transcripts exist next to audio files as .txt)
        from pathlib import Path as _Path

        for idx, cue_path in enumerate(cue_paths, start=1):
            try:
                cue_p = _Path(cue_path)
                if not cue_p.exists():
                    # try relative to puma data root
                    cue_p = _Path("puma_workout_data") / cue_p
                transcript_path = cue_p.with_suffix(".txt")
                if transcript_path.exists():
                    transcript_text = transcript_path.read_text(encoding="utf-8").strip()
                    if transcript_text:
                        chunks.append(
                            RetrievalChunk(
                                chunk_id=f"audio::{exercise_id}::{idx}",
                                text=(f"Audio transcript (cue {idx}): {transcript_text}"),
                                metadata={
                                    "entity_type": "audio",
                                    "workout_id": workout_id,
                                    "workout_title": workout_title,
                                    "section_id": section_id,
                                    "section_title": section_title,
                                    "exercise_id": exercise_id,
                                    "exercise_title": exercise_title,
                                    "cue_index": str(idx),
                                    "audio_path": str(cue_p),
                                },
                            )
                        )
            except Exception:
                # non-fatal: skip bad transcript/cue
                continue

    # Include transcript_chunks table rows (if any)
    try:
        tc_rows = connection.execute(
            "SELECT chunk_id, exercise_id, workout_id, section_id, chunk_index, path, text FROM transcript_chunks ORDER BY workout_id, exercise_id, chunk_index"
        ).fetchall()
        for chunk_id, exercise_id, workout_id, section_id, chunk_index, path, text in tc_rows:
            chunks.append(
                RetrievalChunk(
                    chunk_id=chunk_id,
                    text=(f"Audio transcript chunk: {text}"),
                    metadata={
                        "entity_type": "audio_transcript",
                        "workout_id": workout_id or "",
                        "section_id": section_id or "",
                        "exercise_id": exercise_id,
                        "chunk_index": str(chunk_index),
                        "path": path or "",
                    },
                )
            )
    except Exception:
        # If table does not exist or query fails, skip gracefully
        pass

    return chunks

