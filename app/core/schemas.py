from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Exercise(BaseModel):
    exercise_id: str
    title: str
    local_video: str | None = None
    local_preview: str | None = None
    local_image: str | None = None
    local_audio_cues: list[str] | None = None


class Section(BaseModel):
    section_id: str
    title: str
    exercises: list[Exercise] = Field(default_factory=list)


class WorkoutManifest(BaseModel):
    workout_id: str
    title: str
    local_cover: str
    local_intro: str
    sections: list[Section] = Field(default_factory=list)


class RetrievalChunk(BaseModel):
    chunk_id: str
    text: str
    metadata: dict[str, str]


class RetrievedItem(BaseModel):
    chunk_id: str
    text: str
    metadata: dict[str, str]
    score: float


class WorkoutRenderItem(BaseModel):
    workout_id: str
    workout_title: str
    local_intro: str = ""
    local_cover: str = ""
    score: float


class SectionRenderItem(BaseModel):
    section_id: str
    section_title: str
    workout_id: str
    workout_title: str
    score: float


class ExerciseRenderItem(BaseModel):
    exercise_id: str
    exercise_title: str
    section_id: str
    section_title: str
    workout_id: str
    workout_title: str
    local_video: str = ""
    local_preview: str = ""
    local_image: str = ""
    local_audio_cues: list[str] = Field(default_factory=list)
    score: float


class RenderPayload(BaseModel):
    query: str
    intent: Literal["search", "media_action", "navigation", "fallback"]
    workouts: list[WorkoutRenderItem] = Field(default_factory=list)
    sections: list[SectionRenderItem] = Field(default_factory=list)
    exercises: list[ExerciseRenderItem] = Field(default_factory=list)
    source_chunk_ids: list[str] = Field(default_factory=list)


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    answer: str
    intent: Literal["search", "media_action", "navigation", "fallback"]
    citations: list[RetrievedItem] = Field(default_factory=list)
    render_payload: RenderPayload
