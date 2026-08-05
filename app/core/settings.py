from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    llm_provider: str = Field(default="ollama", alias="LLM_PROVIDER")
    ollama_model: str = Field(default="qwen2.5:3b", alias="OLLAMA_MODEL")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_request_timeout: int = Field(default=10, alias="OLLAMA_REQUEST_TIMEOUT")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-3.5-flash", alias="GEMINI_MODEL")
    puma_data_root: Path = Field(default=Path("puma_workout_data"), alias="PUMA_DATA_ROOT")
    sqlite_db_path: Path = Field(default=Path("storage/workouts.db"), alias="SQLITE_DB_PATH")
    faiss_index_path: Path = Field(default=Path("storage/faiss.index"), alias="FAISS_INDEX_PATH")
    faiss_audio_index_path: Path = Field(default=Path("storage/faiss_audio.index"), alias="FAISS_AUDIO_INDEX_PATH")
    faiss_video_index_path: Path = Field(default=Path("storage/faiss_video.index"), alias="FAISS_VIDEO_INDEX_PATH")
    chunks_json_path: Path = Field(default=Path("storage/chunks.json"), alias="CHUNKS_JSON_PATH")
    chunks_audio_json_path: Path = Field(default=Path("storage/chunks_audio.json"), alias="CHUNKS_AUDIO_JSON_PATH")
    chunks_video_json_path: Path = Field(default=Path("storage/chunks_video.json"), alias="CHUNKS_VIDEO_JSON_PATH")
    embedding_model_name: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        alias="EMBEDDING_MODEL_NAME",
    )
    faiss_top_k: int = Field(default=8, alias="FAISS_TOP_K")
    bm25_top_k: int = Field(default=8, alias="BM25_TOP_K")
    rrf_k: int = Field(default=60, alias="RRF_K")


def get_settings() -> Settings:
    return Settings()
