from __future__ import annotations

from app.core.schemas import RetrievalChunk, WorkoutManifest


def _workout_chunk(workout: WorkoutManifest) -> RetrievalChunk:
    return RetrievalChunk(
        chunk_id=f"workout::{workout.workout_id}",
        text=(
            f"Workout title: {workout.title}. "
            f"Workout ID: {workout.workout_id}. "
            f"Intro video: {workout.local_intro}. "
            f"Cover image: {workout.local_cover}."
        ),
        metadata={
            "entity_type": "workout",
            "workout_id": workout.workout_id,
            "workout_title": workout.title,
            "local_intro": workout.local_intro,
            "local_cover": workout.local_cover,
        },
    )


def chunk_manifests(manifests: list[WorkoutManifest]) -> list[RetrievalChunk]:
    chunks: list[RetrievalChunk] = []
    for workout in manifests:
        chunks.append(_workout_chunk(workout))
        for section in workout.sections:
            chunks.append(
                RetrievalChunk(
                    chunk_id=f"section::{section.section_id}",
                    text=(
                        f"Section title: {section.title}. "
                        f"Section ID: {section.section_id}. "
                        f"Workout title: {workout.title}. "
                        f"Workout ID: {workout.workout_id}."
                    ),
                    metadata={
                        "entity_type": "section",
                        "workout_id": workout.workout_id,
                        "workout_title": workout.title,
                        "section_id": section.section_id,
                        "section_title": section.title,
                    },
                )
            )
            for exercise in section.exercises:
                chunks.append(
                    RetrievalChunk(
                        chunk_id=f"exercise::{exercise.exercise_id}",
                        text=(
                            f"Exercise title: {exercise.title}. "
                            f"Exercise ID: {exercise.exercise_id}. "
                            f"Section title: {section.title}. "
                            f"Section ID: {section.section_id}. "
                            f"Workout title: {workout.title}. "
                            f"Workout ID: {workout.workout_id}. "
                            f"Video: {exercise.local_video or ''}. "
                            f"Preview: {exercise.local_preview or ''}. "
                            f"Image: {exercise.local_image or ''}."
                        ),
                        metadata={
                            "entity_type": "exercise",
                            "workout_id": workout.workout_id,
                            "workout_title": workout.title,
                            "section_id": section.section_id,
                            "section_title": section.title,
                            "exercise_id": exercise.exercise_id,
                            "exercise_title": exercise.title,
                            "local_video": exercise.local_video or "",
                            "local_preview": exercise.local_preview or "",
                            "local_image": exercise.local_image or "",
                            "local_audio_cues": "|".join(exercise.local_audio_cues or []),
                        },
                    )
                )
    return chunks

