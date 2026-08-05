from __future__ import annotations

from app.core.schemas import (
    ExerciseRenderItem,
    RenderPayload,
    RetrievedItem,
    SectionRenderItem,
    WorkoutRenderItem,
)


def _split_audio_cues(raw_value: str) -> list[str]:
    if not raw_value:
        return []
    return [cue for cue in raw_value.split("|") if cue]


def build_render_payload(
    query: str,
    intent: str,
    retrieved_items: list[RetrievedItem],
) -> RenderPayload:
    workouts_by_id: dict[str, WorkoutRenderItem] = {}
    sections_by_id: dict[str, SectionRenderItem] = {}
    exercises_by_id: dict[str, ExerciseRenderItem] = {}
    source_chunk_ids: list[str] = []

    for item in retrieved_items:
        source_chunk_ids.append(item.chunk_id)
        metadata = item.metadata
        entity_type = metadata.get("entity_type", "")

        if entity_type == "workout":
            workout_id = metadata.get("workout_id", "")
            if not workout_id:
                continue
            existing = workouts_by_id.get(workout_id)
            if existing is None or item.score > existing.score:
                workouts_by_id[workout_id] = WorkoutRenderItem(
                    workout_id=workout_id,
                    workout_title=metadata.get("workout_title", ""),
                    local_intro=metadata.get("local_intro", ""),
                    local_cover=metadata.get("local_cover", ""),
                    score=item.score,
                )
            continue

        if entity_type == "section":
            section_id = metadata.get("section_id", "")
            if not section_id:
                continue
            existing = sections_by_id.get(section_id)
            if existing is None or item.score > existing.score:
                sections_by_id[section_id] = SectionRenderItem(
                    section_id=section_id,
                    section_title=metadata.get("section_title", ""),
                    workout_id=metadata.get("workout_id", ""),
                    workout_title=metadata.get("workout_title", ""),
                    score=item.score,
                )
            continue

        if entity_type != "exercise":
            continue

        exercise_id = metadata.get("exercise_id", "")
        if not exercise_id:
            continue
        existing = exercises_by_id.get(exercise_id)
        if existing is None or item.score > existing.score:
            exercises_by_id[exercise_id] = ExerciseRenderItem(
                exercise_id=exercise_id,
                exercise_title=metadata.get("exercise_title", ""),
                section_id=metadata.get("section_id", ""),
                section_title=metadata.get("section_title", ""),
                workout_id=metadata.get("workout_id", ""),
                workout_title=metadata.get("workout_title", ""),
                local_video=metadata.get("local_video", ""),
                local_preview=metadata.get("local_preview", ""),
                local_image=metadata.get("local_image", ""),
                local_audio_cues=_split_audio_cues(metadata.get("local_audio_cues", "")),
                score=item.score,
            )

    normalized_intent = intent if intent in {"search", "media_action", "navigation", "fallback"} else "fallback"
    return RenderPayload(
        query=query,
        intent=normalized_intent,
        workouts=list(workouts_by_id.values()),
        sections=list(sections_by_id.values()),
        exercises=list(exercises_by_id.values()),
        source_chunk_ids=source_chunk_ids,
    )

